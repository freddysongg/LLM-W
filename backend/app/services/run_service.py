from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConfigVersionNotFoundError,
    NoCheckpointError,
    ProjectNotFoundError,
    RunNotFoundError,
    RunStateError,
)
from app.models.artifact import Artifact
from app.models.config_version import ConfigVersion
from app.models.metric_point import MetricPoint
from app.models.model_profile import ModelProfile
from app.models.project import Project
from app.models.run import Run
from app.models.run_stage import RunStage
from app.models.weight_snapshot import WeightSnapshot
from app.schemas.run import (
    CheckpointResponse,
    RunArtifactCompareSummary,
    RunCompareResponse,
    RunCreate,
    RunListResponse,
    RunLogLine,
    RunLogsResponse,
    RunMetricSummary,
    RunResponse,
    RunResumeResponse,
    RunStageResponse,
)
from app.schemas.run_observability import (
    ConfigDiff,
    ConfigSnapshotResponse,
    MetricNamesResponse,
    RunSummaryBatchResponse,
    RunSummaryResponse,
)
from app.schemas.weights import (
    LayerProfile,
    LayerWeightStats,
    ModelProfileResponse,
    WeightSnapshotAllResponse,
    WeightSnapshotResponse,
)
from app.services.config_service import compute_config_diff
from app.services.metrics_service import downsample_to_n

_TRAIN_LOSS_METRIC = "train_loss"
_EVAL_LOSS_METRIC = "eval_loss"
_SPARKLINE_MAX_POINTS = 40

_CANCELLABLE_STATUSES = frozenset({"pending", "running", "paused"})
_PAUSABLE_STATUSES = frozenset({"running"})
_RESUMABLE_STATUSES = frozenset({"failed", "cancelled", "paused", "completed"})
_DELETABLE_STATUSES = frozenset({"completed", "failed", "cancelled"})


async def list_runs(
    *,
    session: AsyncSession,
    project_id: str,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> RunListResponse:
    filters = [Run.project_id == project_id]
    if status is not None:
        filters.append(Run.status == status)

    count_result = await session.execute(select(func.count(Run.id)).where(*filters))
    total = count_result.scalar_one()

    runs_result = await session.execute(
        select(Run).where(*filters).order_by(Run.created_at.desc()).limit(limit).offset(offset)
    )
    runs = list(runs_result.scalars().all())

    return RunListResponse(
        items=[RunResponse.model_validate(r) for r in runs],
        total=total,
        limit=limit,
        offset=offset,
    )


async def get_run(*, session: AsyncSession, run_id: str, project_id: str | None = None) -> Run:
    query = select(Run).where(Run.id == run_id)
    if project_id is not None:
        query = query.where(Run.project_id == project_id)
    result = await session.execute(query)
    run = result.scalar_one_or_none()
    if run is None:
        raise RunNotFoundError(run_id)
    return run


async def create_run(*, session: AsyncSession, project_id: str, payload: RunCreate) -> Run:
    project_result = await session.execute(select(Project).where(Project.id == project_id))
    if project_result.scalar_one_or_none() is None:
        raise ProjectNotFoundError(project_id)

    config_result = await session.execute(
        select(ConfigVersion).where(
            ConfigVersion.id == payload.config_version_id,
            ConfigVersion.project_id == project_id,
        )
    )
    if config_result.scalar_one_or_none() is None:
        raise ConfigVersionNotFoundError(payload.config_version_id)

    now = datetime.now(UTC).isoformat()
    run = Run(
        id=str(uuid.uuid4()),
        project_id=project_id,
        config_version_id=payload.config_version_id,
        parent_run_id=payload.parent_run_id,
        status="pending",
        current_stage=None,
        current_step=0,
        total_steps=None,
        progress_pct=0.0,
        started_at=None,
        completed_at=None,
        failure_reason=None,
        failure_stage=None,
        last_checkpoint_path=None,
        heartbeat_path=None,
        pid=None,
        created_at=now,
        updated_at=now,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def cancel_run(*, session: AsyncSession, run_id: str, project_id: str) -> Run:
    run = await get_run(session=session, run_id=run_id, project_id=project_id)
    if run.status not in _CANCELLABLE_STATUSES:
        raise RunStateError(run_id=run_id, action="cancel", current_status=run.status)
    now = datetime.now(UTC).isoformat()
    run.status = "cancelled"
    run.completed_at = now
    run.updated_at = now
    await session.commit()
    await session.refresh(run)
    return run


async def delete_run(*, session: AsyncSession, run_id: str, project_id: str) -> None:
    run = await get_run(session=session, run_id=run_id, project_id=project_id)
    if run.status not in _DELETABLE_STATUSES:
        raise RunStateError(run_id=run_id, action="delete", current_status=run.status)
    await session.delete(run)
    await session.commit()


async def pause_run(*, session: AsyncSession, run_id: str, project_id: str) -> Run:
    run = await get_run(session=session, run_id=run_id, project_id=project_id)
    if run.status not in _PAUSABLE_STATUSES:
        raise RunStateError(run_id=run_id, action="pause", current_status=run.status)
    run.status = "paused"
    run.updated_at = datetime.now(UTC).isoformat()
    await session.commit()
    await session.refresh(run)
    return run


async def resume_run(*, session: AsyncSession, run_id: str, project_id: str) -> RunResumeResponse:
    run = await get_run(session=session, run_id=run_id, project_id=project_id)
    if run.status not in _RESUMABLE_STATUSES:
        raise RunStateError(run_id=run_id, action="resume", current_status=run.status)

    checkpoint_path = run.last_checkpoint_path
    if not checkpoint_path:
        raise NoCheckpointError(run_id)

    resume_from_step = _extract_step_from_checkpoint_path(checkpoint_path)

    now = datetime.now(UTC).isoformat()
    new_run = Run(
        id=str(uuid.uuid4()),
        project_id=project_id,
        config_version_id=run.config_version_id,
        parent_run_id=run_id,
        status="pending",
        current_stage=None,
        current_step=resume_from_step or 0,
        total_steps=None,
        progress_pct=0.0,
        started_at=None,
        completed_at=None,
        failure_reason=None,
        failure_stage=None,
        last_checkpoint_path=None,
        heartbeat_path=None,
        pid=None,
        created_at=now,
        updated_at=now,
    )
    session.add(new_run)
    await session.commit()
    await session.refresh(new_run)

    return RunResumeResponse(
        new_run_id=new_run.id,
        parent_run_id=run_id,
        resume_from_checkpoint=checkpoint_path,
        resume_from_step=resume_from_step,
        status="pending",
    )


async def get_run_stages(*, session: AsyncSession, run_id: str) -> list[RunStageResponse]:
    result = await session.execute(
        select(RunStage).where(RunStage.run_id == run_id).order_by(RunStage.stage_order)
    )
    stages = list(result.scalars().all())
    return [RunStageResponse.model_validate(s) for s in stages]


async def get_run_metrics(
    *,
    session: AsyncSession,
    run_id: str,
    metric_name: str | None = None,
    step_min: int | None = None,
    step_max: int | None = None,
    limit: int = 1000,
) -> list[MetricPoint]:
    filters = [MetricPoint.run_id == run_id]
    if metric_name is not None:
        filters.append(MetricPoint.metric_name == metric_name)
    if step_min is not None:
        filters.append(MetricPoint.step >= step_min)
    if step_max is not None:
        filters.append(MetricPoint.step <= step_max)
    result = await session.execute(
        select(MetricPoint)
        .where(*filters)
        .order_by(MetricPoint.step, MetricPoint.metric_name)
        .limit(limit)
    )
    return list(result.scalars().all())


def get_run_logs(
    *,
    run_id: str,
    project_directory: str,
    severity: str | None = None,
    stage: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> RunLogsResponse:
    log_path = Path(project_directory) / "logs" / f"{run_id}.log"
    if not log_path.exists():
        return RunLogsResponse(lines=[], total=0, has_more=False)

    all_lines: list[RunLogLine] = []
    try:
        with log_path.open() as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    parsed = json.loads(raw_line)
                    log_line = RunLogLine(
                        severity=parsed.get("severity", "info"),
                        stage=parsed.get("stage"),
                        message=parsed.get("message", raw_line),
                        source=parsed.get("source"),
                        timestamp=parsed.get("timestamp", ""),
                    )
                except (json.JSONDecodeError, KeyError):
                    log_line = RunLogLine(
                        severity="info",
                        stage=None,
                        message=raw_line,
                        source=None,
                        timestamp="",
                    )
                if severity is not None and log_line.severity != severity:
                    continue
                if stage is not None and log_line.stage != stage:
                    continue
                all_lines.append(log_line)
    except OSError:
        return RunLogsResponse(lines=[], total=0, has_more=False)

    total = len(all_lines)
    page = all_lines[offset : offset + limit]
    return RunLogsResponse(lines=page, total=total, has_more=(offset + limit) < total)


async def list_checkpoints(
    *, session: AsyncSession, run_id: str, project_id: str
) -> list[CheckpointResponse]:
    await get_run(session=session, run_id=run_id, project_id=project_id)
    result = await session.execute(
        select(Artifact)
        .where(Artifact.run_id == run_id, Artifact.artifact_type == "checkpoint")
        .order_by(Artifact.created_at)
    )
    artifacts = list(result.scalars().all())
    return [
        CheckpointResponse(
            id=a.id,
            run_id=a.run_id,
            project_id=a.project_id,
            step=_extract_step_from_checkpoint_path(a.file_path),
            file_path=a.file_path,
            file_size_bytes=a.file_size_bytes,
            metadata_json=a.metadata_json,
            is_retained=bool(a.is_retained),
            is_best=bool(a.is_best),
            created_at=a.created_at,
        )
        for a in artifacts
    ]


async def get_config_snapshot(
    *,
    session: AsyncSession,
    project_id: str,
    run_id: str,
) -> ConfigSnapshotResponse:
    run = await get_run(session=session, run_id=run_id, project_id=project_id)

    artifact = (
        await session.execute(
            select(Artifact).where(
                Artifact.run_id == run_id,
                Artifact.artifact_type == "config_snapshot",
            )
        )
    ).scalar_one_or_none()
    if artifact is None:
        raise RunNotFoundError(f"no config snapshot for run {run_id}")

    snapshot_yaml = Path(artifact.file_path).read_text(encoding="utf-8")
    parent = await session.get(ConfigVersion, run.config_version_id)
    parent_yaml = parent.yaml_blob if parent is not None else ""
    diff_dict = compute_config_diff(old_yaml=parent_yaml, new_yaml=snapshot_yaml)

    return ConfigSnapshotResponse(
        run_id=run_id,
        parent_config_version_id=run.config_version_id,
        yaml=snapshot_yaml,
        diff=ConfigDiff(**diff_dict),
    )


async def list_metric_names(
    *,
    session: AsyncSession,
    project_id: str,
    run_id: str,
) -> MetricNamesResponse:
    await get_run(session=session, run_id=run_id, project_id=project_id)
    result = await session.execute(
        select(distinct(MetricPoint.metric_name))
        .where(MetricPoint.run_id == run_id)
        .order_by(MetricPoint.metric_name)
    )
    names = [row[0] for row in result.all()]
    return MetricNamesResponse(metric_names=names)


async def compare_runs(
    *,
    session: AsyncSession,
    project_id: str,
    run_ids: list[str],
) -> RunCompareResponse:
    runs: list[Run] = []
    for run_id in run_ids:
        run = await get_run(session=session, run_id=run_id, project_id=project_id)
        runs.append(run)

    config_by_run: dict[str, dict[str, object]] = {}
    for run in runs:
        cv_result = await session.execute(
            select(ConfigVersion.yaml_blob).where(ConfigVersion.id == run.config_version_id)
        )
        yaml_blob = cv_result.scalar_one_or_none()
        parsed = yaml.safe_load(yaml_blob) if yaml_blob else {}
        config_by_run[run.id] = _flatten_config(parsed or {})

    all_keys: set[str] = set()
    for flat_cfg in config_by_run.values():
        all_keys.update(flat_cfg.keys())

    config_diff: dict[str, object] = {}
    for key in sorted(all_keys):
        values_per_run = {r.id: config_by_run[r.id].get(key) for r in runs}
        unique_values = {str(v) for v in values_per_run.values() if v is not None}
        if len(unique_values) > 1:
            config_diff[key] = values_per_run

    metric_comparison: dict[str, dict[str, RunMetricSummary]] = {}
    for run in runs:
        metrics_result = await session.execute(
            select(MetricPoint).where(MetricPoint.run_id == run.id).order_by(MetricPoint.step)
        )
        metric_points = list(metrics_result.scalars().all())
        by_name: dict[str, list[MetricPoint]] = {}
        for mp in metric_points:
            by_name.setdefault(mp.metric_name, []).append(mp)
        for name, points in by_name.items():
            if name not in metric_comparison:
                metric_comparison[name] = {}
            values = [p.metric_value for p in points]
            metric_comparison[name][run.id] = RunMetricSummary(
                final=values[-1] if values else 0.0,
                min=min(values) if values else 0.0,
                trend=_compute_trend(values),
            )

    artifact_comparison: dict[str, RunArtifactCompareSummary] = {}
    for run in runs:
        artifacts_result = await session.execute(
            select(Artifact).where(
                Artifact.run_id == run.id,
                Artifact.artifact_type == "checkpoint",
            )
        )
        checkpoints = list(artifacts_result.scalars().all())
        total_bytes = sum(a.file_size_bytes for a in checkpoints if a.file_size_bytes is not None)
        artifact_comparison[run.id] = RunArtifactCompareSummary(
            checkpoints=len(checkpoints),
            total_size_mb=round(total_bytes / (1024 * 1024), 2),
        )

    return RunCompareResponse(
        runs=run_ids,
        config_diff={"changed": config_diff} if config_diff else {},
        metric_comparison=metric_comparison,
        artifact_comparison=artifact_comparison,
    )


def _extract_step_from_checkpoint_path(checkpoint_path: str) -> int | None:
    name = Path(checkpoint_path).name
    if name.startswith("checkpoint-"):
        step_str = name[len("checkpoint-") :]
        if step_str.isdigit():
            return int(step_str)
    return None


def _flatten_config(d: dict[str, object], prefix: str = "") -> dict[str, object]:
    result: dict[str, object] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten_config(v, key))
        else:
            result[key] = v
    return result


def _compute_trend(values: list[float]) -> str:
    if len(values) < 3:
        return "stable"
    recent = values[-5:]
    slope = (recent[-1] - recent[0]) / len(recent)
    threshold = abs(recent[0]) * 0.01 if recent[0] != 0.0 else 0.01
    if slope < -threshold:
        return "decreasing"
    if slope > threshold:
        return "increasing"
    return "stable"


async def get_run_summaries(
    *,
    session: AsyncSession,
    project_id: str,
    run_ids: list[str],
) -> RunSummaryBatchResponse:
    summaries: list[RunSummaryResponse] = []
    for run_id in run_ids:
        run_result = await session.execute(
            select(Run).where(Run.id == run_id, Run.project_id == project_id)
        )
        run = run_result.scalar_one_or_none()
        if run is None:
            continue

        train_points = await _fetch_metric_values(
            session=session, run_id=run_id, metric_name=_TRAIN_LOSS_METRIC
        )
        eval_points = await _fetch_metric_values(
            session=session, run_id=run_id, metric_name=_EVAL_LOSS_METRIC
        )

        final_train_loss = train_points[-1] if train_points else None
        final_eval_loss = eval_points[-1] if eval_points else None
        wall_clock_ms = _compute_wall_clock_ms(run=run)
        step_count = await _fetch_max_step(session=session, run_id=run_id)
        sparkline = downsample_to_n(points=train_points, n=_SPARKLINE_MAX_POINTS)

        summaries.append(
            RunSummaryResponse(
                run_id=run_id,
                status=run.status,
                final_train_loss=final_train_loss,
                final_eval_loss=final_eval_loss,
                wall_clock_ms=wall_clock_ms,
                step_count=step_count,
                train_loss_sparkline=sparkline,
            )
        )
    return RunSummaryBatchResponse(runs=summaries)


async def _fetch_metric_values(
    *,
    session: AsyncSession,
    run_id: str,
    metric_name: str,
) -> list[float]:
    result = await session.execute(
        select(MetricPoint.metric_value)
        .where(
            MetricPoint.run_id == run_id,
            MetricPoint.metric_name == metric_name,
        )
        .order_by(MetricPoint.step)
    )
    return [row[0] for row in result.all()]


async def _fetch_max_step(*, session: AsyncSession, run_id: str) -> int:
    result = await session.execute(
        select(func.max(MetricPoint.step)).where(
            MetricPoint.run_id == run_id,
            MetricPoint.metric_name == _TRAIN_LOSS_METRIC,
        )
    )
    value = result.scalar_one_or_none()
    return int(value) if value is not None else 0


def _compute_wall_clock_ms(*, run: Run) -> int:
    if run.started_at is None or run.completed_at is None:
        return 0
    start = datetime.fromisoformat(run.started_at)
    end = datetime.fromisoformat(run.completed_at)
    return int((end - start).total_seconds() * 1000)


async def get_model_profile(
    *,
    session: AsyncSession,
    project_id: str,
    run_id: str,
) -> ModelProfileResponse:
    run = await get_run(session=session, run_id=run_id, project_id=project_id)

    cfg_row = await session.get(ConfigVersion, run.config_version_id)
    if cfg_row is None or not cfg_row.yaml_blob:
        raise RunNotFoundError(f"no config for run {run_id}")
    parsed_cfg = yaml.safe_load(cfg_row.yaml_blob)
    model_block = parsed_cfg.get("model", {}) if isinstance(parsed_cfg, dict) else {}
    model_id = model_block.get("model_id", "")

    profile = (
        await session.execute(
            select(ModelProfile).where(
                ModelProfile.project_id == project_id,
                ModelProfile.model_id == model_id,
            )
        )
    ).scalar_one_or_none()
    if profile is None or profile.layers_json is None:
        raise RunNotFoundError(f"no model profile for run {run_id}")

    raw_layers = json.loads(profile.layers_json)
    return ModelProfileResponse(
        run_id=run_id,
        total_params=profile.parameter_count or 0,
        trainable_params=profile.trainable_count or 0,
        layers=[LayerProfile(**layer) for layer in raw_layers],
    )


async def list_weight_snapshots(
    *,
    session: AsyncSession,
    project_id: str,
    run_id: str,
    layer_name: str | None,
) -> WeightSnapshotResponse | WeightSnapshotAllResponse:
    await get_run(session=session, run_id=run_id, project_id=project_id)
    query = select(WeightSnapshot).where(WeightSnapshot.run_id == run_id)
    if layer_name is not None:
        query = query.where(WeightSnapshot.layer_name == layer_name)
    query = query.order_by(WeightSnapshot.step)
    rows = (await session.execute(query)).scalars().all()

    if layer_name is not None:
        return WeightSnapshotResponse(
            run_id=run_id,
            layer_name=layer_name,
            points=[
                LayerWeightStats(
                    step=row.step,
                    mean=row.mean,
                    std=row.std,
                    norm=row.norm,
                    min_val=row.min_val,
                    max_val=row.max_val,
                )
                for row in rows
            ],
        )

    by_layer: dict[str, list[LayerWeightStats]] = {}
    for row in rows:
        by_layer.setdefault(row.layer_name, []).append(
            LayerWeightStats(
                step=row.step,
                mean=row.mean,
                std=row.std,
                norm=row.norm,
                min_val=row.min_val,
                max_val=row.max_val,
            )
        )
    return WeightSnapshotAllResponse(run_id=run_id, snapshots_by_layer=by_layer)
