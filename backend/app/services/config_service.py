from __future__ import annotations

import hashlib
import json
from typing import Any

import yaml
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConfigValidationError, ConfigVersionNotFoundError
from app.models.config_version import ConfigVersion
from app.models.project import Project
from app.schemas.config_version import (
    ConfigDiffResponse,
    ConfigValidationResponse,
    ConfigVersionCreate,
    ConfigVersionListResponse,
    ConfigVersionResponse,
)
from app.schemas.workbench_config import WorkbenchConfig


async def list_config_versions(
    *,
    session: AsyncSession,
    project_id: str,
    limit: int = 20,
    offset: int = 0,
) -> ConfigVersionListResponse:
    count_result = await session.execute(
        select(func.count()).where(ConfigVersion.project_id == project_id)
    )
    total = count_result.scalar_one()

    result = await session.execute(
        select(ConfigVersion)
        .where(ConfigVersion.project_id == project_id)
        .order_by(ConfigVersion.version_number.desc())
        .limit(limit)
        .offset(offset)
    )
    versions = list(result.scalars().all())
    items = [ConfigVersionResponse.model_validate(v) for v in versions]

    return ConfigVersionListResponse(items=items, total=total, limit=limit, offset=offset)


async def get_active_config_version(
    *, session: AsyncSession, project_id: str
) -> ConfigVersionResponse:
    project_result = await session.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()
    if project is None or project.active_config_version_id is None:
        raise ConfigVersionNotFoundError(f"active config for project {project_id}")

    return await get_config_version(
        session=session,
        project_id=project_id,
        version_id=project.active_config_version_id,
    )


async def get_config_version(
    *, session: AsyncSession, project_id: str, version_id: str
) -> ConfigVersionResponse:
    result = await session.execute(
        select(ConfigVersion).where(
            ConfigVersion.id == version_id,
            ConfigVersion.project_id == project_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise ConfigVersionNotFoundError(version_id)

    return ConfigVersionResponse.model_validate(version)


async def create_config_version(
    *,
    session: AsyncSession,
    project_id: str,
    payload: ConfigVersionCreate,
) -> ConfigVersion:
    _validate_yaml_or_raise(payload.yaml_content)

    yaml_hash = "sha256:" + hashlib.sha256(payload.yaml_content.encode()).hexdigest()

    count_result = await session.execute(
        select(func.count()).where(ConfigVersion.project_id == project_id)
    )
    version_number = (count_result.scalar_one() or 0) + 1

    diff_from_prev: str | None = None
    if version_number > 1:
        prev_result = await session.execute(
            select(ConfigVersion)
            .where(ConfigVersion.project_id == project_id)
            .order_by(ConfigVersion.version_number.desc())
            .limit(1)
        )
        prev_version = prev_result.scalar_one_or_none()
        if prev_version is not None:
            prev_config = yaml.safe_load(prev_version.yaml_blob)
            new_config = yaml.safe_load(payload.yaml_content)
            diff = _compute_diff(prev_config or {}, new_config or {})
            diff_from_prev = json.dumps(diff)

    import uuid
    from datetime import UTC, datetime

    version = ConfigVersion(
        id=str(uuid.uuid4()),
        project_id=project_id,
        version_number=version_number,
        yaml_blob=payload.yaml_content,
        yaml_hash=yaml_hash,
        diff_from_prev=diff_from_prev,
        source_tag=payload.source_tag,
        source_detail=payload.source_detail,
        created_at=datetime.now(UTC).isoformat(),
    )
    session.add(version)
    await session.flush()

    return version


async def diff_config_versions(
    *,
    session: AsyncSession,
    project_id: str,
    version_a_id: str,
    version_b_id: str,
) -> ConfigDiffResponse:
    version_a = await get_config_version(
        session=session, project_id=project_id, version_id=version_a_id
    )
    version_b = await get_config_version(
        session=session, project_id=project_id, version_id=version_b_id
    )

    config_a_result = await session.execute(
        select(ConfigVersion.yaml_blob).where(ConfigVersion.id == version_a_id)
    )
    config_b_result = await session.execute(
        select(ConfigVersion.yaml_blob).where(ConfigVersion.id == version_b_id)
    )
    yaml_a = config_a_result.scalar_one()
    yaml_b = config_b_result.scalar_one()

    dict_a = yaml.safe_load(yaml_a) or {}
    dict_b = yaml.safe_load(yaml_b) or {}

    return ConfigDiffResponse(
        version_a_id=version_a.id,
        version_b_id=version_b.id,
        diff=_compute_diff(dict_a, dict_b),
    )


def validate_config(*, yaml_content: str) -> ConfigValidationResponse:
    errors: list[str] = []

    try:
        parsed = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        return ConfigValidationResponse(is_valid=False, errors=[str(exc)])

    if not isinstance(parsed, dict):
        return ConfigValidationResponse(
            is_valid=False, errors=["Config must be a YAML mapping"]
        )

    try:
        WorkbenchConfig.model_validate(parsed)
    except ValidationError as exc:
        errors = [f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in exc.errors()]

    return ConfigValidationResponse(is_valid=len(errors) == 0, errors=errors)


async def get_config_yaml(
    *, session: AsyncSession, project_id: str, version_id: str
) -> str:
    result = await session.execute(
        select(ConfigVersion.yaml_blob).where(
            ConfigVersion.id == version_id,
            ConfigVersion.project_id == project_id,
        )
    )
    yaml_blob = result.scalar_one_or_none()
    if yaml_blob is None:
        raise ConfigVersionNotFoundError(version_id)

    return yaml_blob


def _validate_yaml_or_raise(yaml_content: str) -> None:
    try:
        parsed = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        raise ConfigValidationError(str(exc)) from exc

    if not isinstance(parsed, dict):
        raise ConfigValidationError("Config must be a YAML mapping")


def _flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten_dict(v, key))
        else:
            result[key] = v
    return result


def _compute_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_flat = _flatten_dict(old)
    new_flat = _flatten_dict(new)
    all_keys = set(old_flat) | set(new_flat)

    changed: dict[str, Any] = {}
    added: dict[str, Any] = {}
    removed: dict[str, Any] = {}

    for key in sorted(all_keys):
        if key not in old_flat:
            added[key] = new_flat[key]
        elif key not in new_flat:
            removed[key] = old_flat[key]
        elif old_flat[key] != new_flat[key]:
            changed[key] = {"old": old_flat[key], "new": new_flat[key]}

    result: dict[str, Any] = {}
    if changed:
        result["changed"] = changed
    if added:
        result["added"] = added
    if removed:
        result["removed"] = removed

    return result
