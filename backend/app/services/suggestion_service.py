from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConfigVersionNotFoundError,
    ProjectNotFoundError,
    SuggestionNotFoundError,
)
from app.models.config_version import ConfigVersion
from app.models.decision_log import DecisionLog
from app.models.metric_point import MetricPoint
from app.models.project import Project
from app.models.suggestion import AISuggestion
from app.schemas.config_version import ConfigVersionCreate
from app.schemas.suggestion import SuggestionListResponse, SuggestionResponse
from app.services import config_service
from app.services.ai_recommender import AISuggestionCreate, build_engine
from app.services.settings_service import get_settings


async def _get_project(*, session: AsyncSession, project_id: str) -> Project:
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError(project_id)
    return project


async def _get_suggestion_orm(
    *, session: AsyncSession, project_id: str, suggestion_id: str
) -> AISuggestion:
    result = await session.execute(
        select(AISuggestion).where(
            AISuggestion.id == suggestion_id,
            AISuggestion.project_id == project_id,
        )
    )
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise SuggestionNotFoundError(suggestion_id)
    return suggestion


def _to_response(suggestion: AISuggestion) -> SuggestionResponse:
    return SuggestionResponse.model_validate(suggestion)


async def list_suggestions(
    *,
    session: AsyncSession,
    project_id: str,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SuggestionListResponse:
    count_q = select(func.count()).where(AISuggestion.project_id == project_id)
    items_q = (
        select(AISuggestion)
        .where(AISuggestion.project_id == project_id)
        .order_by(AISuggestion.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status:
        count_q = count_q.where(AISuggestion.status == status)
        items_q = items_q.where(AISuggestion.status == status)

    total = (await session.execute(count_q)).scalar_one()
    rows = list((await session.execute(items_q)).scalars().all())
    return SuggestionListResponse(items=[_to_response(s) for s in rows], total=total)


async def get_suggestion(
    *, session: AsyncSession, project_id: str, suggestion_id: str
) -> SuggestionResponse:
    suggestion = await _get_suggestion_orm(
        session=session, project_id=project_id, suggestion_id=suggestion_id
    )
    return _to_response(suggestion)


async def _fetch_run_metrics(
    *, session: AsyncSession, run_id: str, limit: int = 500
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(MetricPoint)
        .where(MetricPoint.run_id == run_id)
        .order_by(MetricPoint.step.asc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [{"step": r.step, "metric_name": r.metric_name, "value": r.value} for r in rows]


def _set_nested(config: dict[str, Any], dot_path: str, value: Any) -> None:
    """Set a value in a nested dict using dot notation."""
    parts = dot_path.split(".")
    node = config
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value


def _apply_config_diff(
    config: dict[str, Any], config_diff: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Apply a suggestion config_diff (flat dot-notation paths) to a config dict."""
    import copy

    updated = copy.deepcopy(config)
    for path, change in config_diff.items():
        suggested = change.get("suggested")
        if suggested is not None:
            _set_nested(updated, path, suggested)
    return updated


async def _store_suggestion(
    *,
    session: AsyncSession,
    project_id: str,
    source_run_id: str | None,
    create: AISuggestionCreate,
) -> AISuggestion:
    now = datetime.now(UTC).isoformat()
    suggestion = AISuggestion(
        id=str(uuid.uuid4()),
        project_id=project_id,
        source_run_id=source_run_id,
        provider=create.provider,
        config_diff=json.dumps(create.config_diff),
        rationale=create.rationale,
        evidence_json=json.dumps(create.evidence) if create.evidence else None,
        expected_effect=create.expected_effect,
        tradeoffs=create.tradeoffs,
        confidence=create.confidence,
        risk_level=create.risk_level,
        status="pending",
        applied_config_version_id=None,
        created_at=now,
        resolved_at=None,
    )
    session.add(suggestion)
    await session.flush()
    return suggestion


async def generate_suggestions(
    *,
    session: AsyncSession,
    project_id: str,
    source_run_id: str | None = None,
    notes: str | None = None,
) -> SuggestionListResponse:
    project = await _get_project(session=session, project_id=project_id)

    if project.active_config_version_id is None:
        raise ConfigVersionNotFoundError(f"no active config for project {project_id}")

    config_version_result = await session.execute(
        select(ConfigVersion).where(ConfigVersion.id == project.active_config_version_id)
    )
    config_version = config_version_result.scalar_one_or_none()
    if config_version is None:
        raise ConfigVersionNotFoundError(project.active_config_version_id)

    config: dict[str, Any] = yaml.safe_load(config_version.yaml_blob) or {}

    run_metrics: list[dict[str, Any]] = []
    if source_run_id:
        run_metrics = await _fetch_run_metrics(session=session, run_id=source_run_id)

    current_settings = get_settings()
    # Retrieve raw key from overrides (settings_service stores the plaintext key in _overrides)
    from app.core.config import settings as _app_settings
    from app.services.settings_service import _overrides as _settings_overrides

    raw_api_key: str | None = _settings_overrides.get("ai_api_key") or _app_settings.ai_api_key
    engine = build_engine(
        provider=current_settings.ai_provider,
        api_key=raw_api_key,
        model_id=current_settings.ai_model_id,
        base_url=current_settings.ai_base_url,
    )

    creates = await engine.generate_recommendations(
        config=config,
        run_metrics=run_metrics,
        dataset_profile={},
        comparison_data=None,
        notes=notes,
    )

    stored = []
    for create in creates:
        suggestion = await _store_suggestion(
            session=session,
            project_id=project_id,
            source_run_id=source_run_id,
            create=create,
        )
        stored.append(suggestion)

    await session.commit()
    return SuggestionListResponse(
        items=[_to_response(s) for s in stored],
        total=len(stored),
    )


async def accept_suggestion(
    *, session: AsyncSession, project_id: str, suggestion_id: str
) -> SuggestionResponse:
    project = await _get_project(session=session, project_id=project_id)
    suggestion = await _get_suggestion_orm(
        session=session, project_id=project_id, suggestion_id=suggestion_id
    )

    if project.active_config_version_id is None:
        raise ConfigVersionNotFoundError(f"no active config for project {project_id}")

    config_version_result = await session.execute(
        select(ConfigVersion).where(ConfigVersion.id == project.active_config_version_id)
    )
    config_version = config_version_result.scalar_one_or_none()
    if config_version is None:
        raise ConfigVersionNotFoundError(project.active_config_version_id)

    current_config: dict[str, Any] = yaml.safe_load(config_version.yaml_blob) or {}
    config_diff: dict[str, dict[str, Any]] = json.loads(suggestion.config_diff)
    updated_config = _apply_config_diff(current_config, config_diff)
    updated_yaml = yaml.dump(updated_config, default_flow_style=False, allow_unicode=True)

    new_version = await config_service.create_config_version(
        session=session,
        project_id=project_id,
        payload=ConfigVersionCreate(
            yaml_content=updated_yaml,
            source_tag="ai_suggestion",
            source_detail=f"Applied suggestion {suggestion_id}",
        ),
    )

    project.active_config_version_id = new_version.id
    now = datetime.now(UTC).isoformat()
    suggestion.status = "accepted"
    suggestion.applied_config_version_id = new_version.id
    suggestion.resolved_at = now

    log = DecisionLog(
        id=str(uuid.uuid4()),
        project_id=project_id,
        action_type="suggestion_accepted",
        actor="user",
        target_type="ai_suggestion",
        target_id=suggestion_id,
        before_state=json.dumps({"status": "pending"}),
        after_state=json.dumps(
            {"status": "accepted", "applied_config_version_id": new_version.id}
        ),
        notes=f"New config version {new_version.id} created from AI suggestion",
        created_at=now,
    )
    session.add(log)
    await session.commit()
    return _to_response(suggestion)


async def reject_suggestion(
    *, session: AsyncSession, project_id: str, suggestion_id: str
) -> SuggestionResponse:
    suggestion = await _get_suggestion_orm(
        session=session, project_id=project_id, suggestion_id=suggestion_id
    )

    now = datetime.now(UTC).isoformat()
    suggestion.status = "rejected"
    suggestion.resolved_at = now

    log = DecisionLog(
        id=str(uuid.uuid4()),
        project_id=project_id,
        action_type="suggestion_rejected",
        actor="user",
        target_type="ai_suggestion",
        target_id=suggestion_id,
        before_state=json.dumps({"status": "pending"}),
        after_state=json.dumps({"status": "rejected"}),
        notes=None,
        created_at=now,
    )
    session.add(log)
    await session.commit()
    return _to_response(suggestion)
