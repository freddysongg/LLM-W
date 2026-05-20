from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal as _signal
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.events import event_bus
from app.core.exceptions import (
    ConfigVersionNotFoundError,
    ProjectNotFoundError,
)
from app.models.artifact import Artifact
from app.models.config_version import ConfigVersion
from app.models.metric_point import MetricPoint
from app.models.model_profile import ModelProfile
from app.models.project import Project
from app.models.run import Run
from app.models.run_stage import RunStage
from app.models.weight_snapshot import WeightSnapshot
from app.schemas.run import RunCreate, RunResponse
from app.schemas.workbench_config import ExecutionConfig
from app.services import settings_service, suggestion_service
from app.services.config_service import serialize_config_yaml_snapshot
from app.services.storage_manager import (
    apply_retention_after_checkpoint,
    run_project_cleanup,
)
from app.services.training_dispatcher import (
    TrainingProcess,
    UnsupportedEnvironmentError,
    dispatch_training,
)

# Hard ceiling for execution.max_estimated_cost_usd. Configs exceeding this are
# rejected at run-creation time so a misconfigured budget can't silently rack up
# a multi-hundred-dollar cloud bill. See plan.md "Cloud Budget Defaults".
_MAX_ALLOWED_COST_USD: float = 5.0

# Modal-published USD-per-second GPU rates (rounded from the per-hour pricing on
# https://modal.com/pricing as of 2025). Used to compute Run.cost_usd at terminal
# transitions. Keys mirror ExecutionConfig.modal_gpu_type literals.
_GPU_USD_PER_SECOND: dict[str, float] = {
    "t4": 0.000164,
    "a10": 0.000306,
    "l40s": 0.000542,
    "a100-40gb": 0.000900,
    "a100-80gb": 0.001067,
    "h100": 0.001442,
}

logger = logging.getLogger(__name__)

_STAGE_ORDER: dict[str, int] = {
    "config_validation": 1,
    "environment_validation": 2,
    "model_resolution": 3,
    "dataset_resolution": 4,
    "dataset_profiling": 5,
    "tokenization_preprocessing": 6,
    "training_preparation": 7,
    "adapter_attachment": 8,
    "training_start": 9,
    "training_progress": 10,
    "evaluation": 11,
    "checkpoint_save": 12,
    "artifact_finalization": 13,
    "completion": 14,
}

_ALL_STAGE_NAMES: list[str] = [
    "config_validation",
    "environment_validation",
    "model_resolution",
    "dataset_resolution",
    "dataset_profiling",
    "tokenization_preprocessing",
    "training_preparation",
    "adapter_attachment",
    "training_start",
    "training_progress",
    "evaluation",
    "checkpoint_save",
    "artifact_finalization",
    "completion",
]

_IS_UNIX = sys.platform != "win32"

# Maps run_id → TrainingProcess handle
_active_processes: dict[str, TrainingProcess] = {}

# Strong references to the orchestration tasks spawned by create_run. Without
# these, Python's event loop only holds weak refs (see asyncio.create_task
# docs) and the GC can silently drop a task mid-flight, leaving a run stuck
# in "pending" with no pid and no trainer ever launched.
_active_tasks: dict[str, asyncio.Task[None]] = {}

# Post-completion analysis tasks fanned out from terminal-state transitions.
# Same weak-ref hazard as `_active_tasks` — without a strong reference here
# the auto-analyze call can disappear before it runs.
_active_analysis_tasks: set[asyncio.Task[None]] = set()


def _log_background_task_exception(task: asyncio.Task[None]) -> None:
    """Surface unhandled exceptions from background tasks.

    Without this, an exception escapes as a GC-time `Task exception was
    never retrieved` warning, with no stack trace tied to the failing run.
    """
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("background task %s raised", task.get_name(), exc_info=exc)


async def list_runs(*, session: AsyncSession, project_id: str) -> list[Run]:
    result = await session.execute(
        select(Run).where(Run.project_id == project_id).order_by(Run.created_at.desc())
    )
    return list(result.scalars().all())


async def get_run(*, session: AsyncSession, run_id: str) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise KeyError(f"Run not found: {run_id}")
    return run


async def get_run_stages(*, session: AsyncSession, run_id: str) -> list[RunStage]:
    result = await session.execute(
        select(RunStage).where(RunStage.run_id == run_id).order_by(RunStage.stage_order)
    )
    return list(result.scalars().all())


async def get_run_metrics(
    *,
    session: AsyncSession,
    run_id: str,
    metric_name: str | None = None,
    step_from: int | None = None,
    step_to: int | None = None,
    limit: int = 1000,
) -> list[MetricPoint]:
    query = select(MetricPoint).where(MetricPoint.run_id == run_id)
    if metric_name is not None:
        query = query.where(MetricPoint.metric_name == metric_name)
    if step_from is not None:
        query = query.where(MetricPoint.step >= step_from)
    if step_to is not None:
        query = query.where(MetricPoint.step <= step_to)
    query = query.order_by(MetricPoint.step, MetricPoint.metric_name).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def compare_runs(*, session: AsyncSession, run_ids: list[str]) -> dict[str, Any]:
    runs = []
    for run_id in run_ids:
        run = await session.get(Run, run_id)
        if run is not None:
            runs.append(RunResponse.model_validate(run))

    metrics_by_run: dict[str, list[dict[str, Any]]] = {}
    for run_id in run_ids:
        points = await get_run_metrics(session=session, run_id=run_id)
        metrics_by_run[run_id] = [
            {
                "step": p.step,
                "epoch": p.epoch,
                "metric_name": p.metric_name,
                "metric_value": p.metric_value,
            }
            for p in points
        ]

    return {"runs": [r.model_dump() for r in runs], "metrics": metrics_by_run}


async def create_run(
    *,
    session: AsyncSession,
    project_id: str,
    payload: RunCreate,
) -> Run:
    project = await session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(project_id)

    config_version = await session.get(ConfigVersion, payload.config_version_id)
    if config_version is None:
        raise ConfigVersionNotFoundError(payload.config_version_id)

    # Validate execution config before creating the run — avoids orphaned failed runs.
    raw_config: dict[str, object] = yaml.safe_load(config_version.yaml_blob) or {}
    execution_raw = raw_config.get("execution", {})
    execution_cfg = ExecutionConfig.model_validate(
        execution_raw if isinstance(execution_raw, dict) else {}
    )
    _validate_execution_for_run(execution=execution_cfg)
    if execution_cfg.environment == "modal" and execution_cfg.data_policy == "sanitized_cloud":
        _require_sanitized_artifact(project_dir=Path(project.directory_path))

    run_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    run = Run(
        id=run_id,
        project_id=project_id,
        config_version_id=payload.config_version_id,
        parent_run_id=payload.parent_run_id,
        status="pending",
        current_step=0,
        progress_pct=0.0,
        heartbeat_path=str(settings.projects_dir / project.name / ".heartbeat"),
        environment=execution_cfg.environment,
        modal_gpu_type=(
            execution_cfg.modal_gpu_type if execution_cfg.environment == "modal" else None
        ),
        device=execution_cfg.device,
        created_at=now,
        updated_at=now,
    )
    session.add(run)

    # Pre-create all 14 stage rows in pending state
    for stage_name in _ALL_STAGE_NAMES:
        stage_row = RunStage(
            id=str(uuid.uuid4()),
            run_id=run_id,
            stage_name=stage_name,
            stage_order=_STAGE_ORDER[stage_name],
            status="pending",
            created_at=now,
        )
        session.add(stage_row)

    await session.commit()
    await session.refresh(run)

    project_dir = Path(project.directory_path)

    await _write_config_snapshot(
        run_id=run.id,
        project_id=project_id,
        project_dir=project_dir,
        config_yaml=config_version.yaml_blob,
    )

    execution_summary = _execution_summary(execution=execution_cfg)
    logger.info(
        "run_created",
        extra={
            "run_id": run_id,
            "project_id": project_id,
            "execution": execution_summary,
        },
    )
    await event_bus.publish(
        event_type=f"project.{project_id}.ws",
        payload={
            "channel": "run_state",
            "event": "run_created",
            "runId": run_id,
            "timestamp": now,
            "payload": {
                "runId": run_id,
                "configVersionId": payload.config_version_id,
                "status": "pending",
                "execution": execution_summary,
            },
        },
    )

    # Launch trainer subprocess asynchronously
    resume_checkpoint: str | None = None
    if payload.parent_run_id:
        parent = await session.get(Run, payload.parent_run_id)
        if parent is not None and parent.last_checkpoint_path:
            resume_checkpoint = parent.last_checkpoint_path

    config_path = _resolve_config_path(config_version=config_version, project_dir=project_dir)

    task = asyncio.create_task(
        _run_trainer_subprocess(
            run_id=run_id,
            project_id=project_id,
            config_path=config_path,
            project_dir=project_dir,
            resume_from_checkpoint=resume_checkpoint,
        ),
        name=f"trainer-orchestration-{run_id}",
    )
    _active_tasks[run_id] = task

    def _on_task_done(completed: asyncio.Task[None]) -> None:
        _active_tasks.pop(run_id, None)
        _log_background_task_exception(completed)

    task.add_done_callback(_on_task_done)

    return run


def _validate_execution_for_run(*, execution: ExecutionConfig) -> None:
    """Reject configs that would launch an unsupported, unsafe, or over-budget run.

    Local runs are always allowed. Modal runs require sanitized data, a configured
    Modal token pair, and an estimated cost within the hard ceiling.
    """
    if execution.environment == "local":
        return
    if execution.environment != "modal":
        raise UnsupportedEnvironmentError(
            f"Execution environment '{execution.environment}' is not supported. "
            "Set execution.environment to 'local' or 'modal'."
        )

    if execution.data_policy == "local_raw":
        raise UnsupportedEnvironmentError(
            "Modal runs require execution.data_policy='sanitized_cloud'. "
            "Raw local logs must not be uploaded to cloud GPUs — sanitize the "
            "dataset first or switch execution.environment to 'local'."
        )

    if execution.max_estimated_cost_usd > _MAX_ALLOWED_COST_USD:
        raise UnsupportedEnvironmentError(
            f"execution.max_estimated_cost_usd ({execution.max_estimated_cost_usd}) "
            f"exceeds the hard cap of ${_MAX_ALLOWED_COST_USD}. Lower the budget or "
            "raise the cap explicitly."
        )

    # The user-supplied budget is a self-report; the actual ceiling is GPU rate ×
    # sandbox timeout, since the sandbox can run for the full `max_run_minutes`
    # window regardless of what the user estimated. Reject when that ceiling
    # exceeds the cap so a slow H100 config can't outspend the budget.
    gpu_rate = _GPU_USD_PER_SECOND.get(execution.modal_gpu_type, 0.0)
    worst_case_cost_usd = execution.max_run_minutes * 60 * gpu_rate
    if worst_case_cost_usd > _MAX_ALLOWED_COST_USD:
        raise UnsupportedEnvironmentError(
            f"Worst-case spend for modal_gpu_type='{execution.modal_gpu_type}' over "
            f"max_run_minutes={execution.max_run_minutes} is "
            f"${worst_case_cost_usd:.2f}, which exceeds the hard cap of "
            f"${_MAX_ALLOWED_COST_USD}. Lower max_run_minutes or choose a cheaper GPU."
        )

    if settings_service.get_modal_credentials() is None:
        raise UnsupportedEnvironmentError(
            "Modal training requires modal_token_id and modal_token_secret to be "
            "configured under workbench settings before launching a cloud run."
        )


_SANITIZED_DATASET_FILENAME = "sanitized.jsonl"


def _require_sanitized_artifact(*, project_dir: Path) -> None:
    """Refuse Modal runs that don't have a sanitized dataset artifact on disk.

    The `sanitized_cloud` data policy is the contract that only redacted rows
    leave the host. Without a persisted sanitized artifact, the only thing the
    adapter could upload is the raw `datasets/` directory — which would violate
    the policy. This gate enforces that the artifact must exist before the run
    is created. Operators produce it via POST /api/v1/projects/{id}/datasets/sanitize.
    """
    artifact = project_dir / "datasets" / _SANITIZED_DATASET_FILENAME
    if not artifact.is_file():
        raise UnsupportedEnvironmentError(
            f"Modal runs with data_policy='sanitized_cloud' require a sanitized "
            f"artifact at {artifact}. Call POST /api/v1/projects/{{project_id}}/"
            f"datasets/sanitize with persist=true before launching the run."
        )


def _execution_summary(*, execution: ExecutionConfig) -> dict[str, Any]:
    """Return a minimal, JSON-serializable view of the execution config.

    Surfaced via the run_created WebSocket event so the UI and operator logs
    can show GPU type, environment, and the budget that gated this run.
    """
    return {
        "environment": execution.environment,
        "modalGpuType": execution.modal_gpu_type,
        "maxRunMinutes": execution.max_run_minutes,
        "maxEstimatedCostUsd": execution.max_estimated_cost_usd,
        "dataPolicy": execution.data_policy,
    }


def _resolve_config_path(*, config_version: ConfigVersion, project_dir: Path) -> Path:
    config_path = project_dir / "configs" / f"version-{config_version.version_number}.yaml"
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_version.yaml_blob)
    return config_path


def _load_execution_config(*, config_path: Path) -> ExecutionConfig:
    raw_config: dict[str, object] = yaml.safe_load(config_path.read_text()) or {}
    execution_raw = raw_config.get("execution", {})
    execution_dict = execution_raw if isinstance(execution_raw, dict) else {}
    return ExecutionConfig.model_validate(execution_dict)


async def _load_run_started_iso(*, run_id: str) -> str | None:
    """Return the canonical run-start ISO timestamp used as the cost-meter anchor.

    Prefers `Run.started_at` (written on the first `stage_enter` event, i.e. when
    the trainer actually entered a stage) and falls back to `Run.created_at` for
    runs that crashed before any stage was reported.
    """
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return None
        return run.started_at or run.created_at


async def _update_run_status(
    *,
    run_id: str,
    status: str,
    current_step: int | None = None,
    total_steps: int | None = None,
    progress_pct: float | None = None,
    current_stage: str | None = None,
    failure_reason: str | None = None,
    failure_stage: str | None = None,
    pid: int | None = None,
    last_checkpoint_path: str | None = None,
    cost_usd: float | None = None,
    wall_clock_s: float | None = None,
    started_at: str | None = None,
) -> None:
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        now = datetime.now(UTC).isoformat()
        run.status = status
        run.updated_at = now
        if status in ("completed", "failed", "cancelled"):
            run.completed_at = now
        if current_step is not None:
            run.current_step = current_step
        if total_steps is not None:
            run.total_steps = total_steps
        if progress_pct is not None:
            run.progress_pct = progress_pct
        if current_stage is not None:
            run.current_stage = current_stage
        if failure_reason is not None:
            run.failure_reason = failure_reason
        if failure_stage is not None:
            run.failure_stage = failure_stage
        if pid is not None:
            run.pid = pid
        if last_checkpoint_path is not None:
            run.last_checkpoint_path = last_checkpoint_path
        if cost_usd is not None:
            run.cost_usd = cost_usd
        if wall_clock_s is not None:
            run.wall_clock_s = wall_clock_s
        # First-stage write only — later stages must not reset the cost anchor.
        if started_at is not None and run.started_at is None:
            run.started_at = started_at
        await session.commit()


def _compute_run_cost(
    *,
    execution: ExecutionConfig,
    started_iso: str,
    ended_iso: str,
) -> tuple[float, float]:
    """Return (wall_clock_seconds, cost_usd) for a terminal run.

    Cost is zero for local execution. For Modal runs, cost is the elapsed wall
    clock seconds multiplied by the published per-second GPU rate. Wall clock
    is clamped at zero to absorb clock skew that would otherwise produce a
    negative cost.
    """
    started = datetime.fromisoformat(started_iso)
    ended = datetime.fromisoformat(ended_iso)
    wall_clock_s = max(0.0, (ended - started).total_seconds())
    if execution.environment != "modal":
        return (wall_clock_s, 0.0)
    rate = _GPU_USD_PER_SECOND.get(execution.modal_gpu_type, 0.0)
    return (wall_clock_s, wall_clock_s * rate)


async def _update_stage(
    *,
    run_id: str,
    stage_name: str,
    status: str,
    started_at: str | None = None,
    completed_at: str | None = None,
    duration_ms: int | None = None,
    output_summary: str | None = None,
    warnings_json: str | None = None,
) -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(RunStage).where(RunStage.run_id == run_id, RunStage.stage_name == stage_name)
        )
        stage_row = result.scalar_one_or_none()
        if stage_row is None:
            return
        stage_row.status = status
        if started_at is not None:
            stage_row.started_at = started_at
        if completed_at is not None:
            stage_row.completed_at = completed_at
        if duration_ms is not None:
            stage_row.duration_ms = duration_ms
        if output_summary is not None:
            stage_row.output_summary = output_summary
        if warnings_json is not None:
            stage_row.warnings_json = warnings_json
        await session.commit()


async def _record_metric_batch(
    *, run_id: str, step: int, epoch: float, metrics: dict[str, float]
) -> None:
    async with async_session_factory() as session:
        now = datetime.now(UTC).isoformat()
        for name, value in metrics.items():
            point = MetricPoint(
                id=str(uuid.uuid4()),
                run_id=run_id,
                step=step,
                epoch=epoch,
                metric_name=name,
                metric_value=value,
                recorded_at=now,
            )
            session.add(point)
        await session.commit()


async def _mark_pending_stages_skipped(*, run_id: str) -> None:
    """Mark all pending stages as skipped after a run reaches a terminal state."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(RunStage).where(RunStage.run_id == run_id, RunStage.status == "pending")
        )
        pending_stages = list(result.scalars().all())
        for stage_row in pending_stages:
            stage_row.status = "skipped"
        if pending_stages:
            await session.commit()


async def _record_artifact(
    *,
    run_id: str,
    project_id: str,
    artifact_type: str,
    file_path: str,
    size_bytes: int,
    is_best: int = 0,
) -> None:
    async with async_session_factory() as session:
        now = datetime.now(UTC).isoformat()
        artifact = Artifact(
            id=str(uuid.uuid4()),
            run_id=run_id,
            project_id=project_id,
            artifact_type=artifact_type,
            file_path=file_path,
            file_size_bytes=size_bytes,
            is_retained=1,
            is_best=is_best,
            created_at=now,
        )
        session.add(artifact)
        await session.commit()


async def _extract_model_identity(*, session: AsyncSession, run: Run) -> tuple[str, str, str]:
    """Derive (model_id, source, family) from the run's ConfigVersion YAML.

    The Run table has no direct model columns, so identity is sourced from the
    immutable config snapshot that was used to launch the run.
    """
    config_version = await session.get(ConfigVersion, run.config_version_id)
    if config_version is None or not config_version.yaml_blob:
        return ("", "", "")
    parsed: object = yaml.safe_load(config_version.yaml_blob)
    if not isinstance(parsed, dict):
        return ("", "", "")
    model_block = parsed.get("model", {})
    if not isinstance(model_block, dict):
        return ("", "", "")
    return (
        str(model_block.get("model_id", "") or ""),
        str(model_block.get("source", "") or ""),
        str(model_block.get("family", "") or ""),
    )


async def _persist_model_profile(
    *,
    run_id: str,
    project_id: str,
    total_params: int,
    trainable_params: int,
    layers: list[dict[str, Any]],
) -> None:
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return

        model_id, model_source, model_family = await _extract_model_identity(
            session=session, run=run
        )

        existing = (
            await session.execute(
                select(ModelProfile).where(
                    ModelProfile.project_id == project_id,
                    ModelProfile.model_id == model_id,
                )
            )
        ).scalar_one_or_none()

        now = datetime.now(UTC).isoformat()
        if existing is None:
            session.add(
                ModelProfile(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    source=model_source,
                    model_id=model_id,
                    family=model_family,
                    parameter_count=total_params,
                    trainable_count=trainable_params,
                    layers_json=json.dumps(layers),
                    created_at=now,
                    updated_at=now,
                )
            )
        elif existing.layers_json is None:
            existing.layers_json = json.dumps(layers)
            existing.parameter_count = existing.parameter_count or total_params
            existing.trainable_count = existing.trainable_count or trainable_params
            existing.updated_at = now

        await session.commit()


async def _persist_weight_stats(
    *,
    run_id: str,
    step: int,
    stats: dict[str, dict[str, float]],
) -> None:
    async with async_session_factory() as session:
        now = datetime.now(UTC).isoformat()
        session.add_all(
            [
                WeightSnapshot(
                    run_id=run_id,
                    step=step,
                    layer_name=layer_name,
                    mean=values["mean"],
                    std=values["std"],
                    norm=values["norm"],
                    min_val=values["min"],
                    max_val=values["max"],
                    created_at=now,
                )
                for layer_name, values in stats.items()
            ]
        )
        await session.commit()


async def _run_final_retention_sweep(
    *,
    session: AsyncSession,
    project_id: str,
) -> None:
    """On run termination, invoke the project-level cleanup which honors
    delete_intermediates_after_completion per config."""
    await run_project_cleanup(session=session, project_id=project_id)


async def _write_config_snapshot(
    *,
    run_id: str,
    project_id: str,
    project_dir: Path,
    config_yaml: str,
) -> None:
    run_dir = project_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = run_dir / "config.yaml"
    effective_yaml = serialize_config_yaml_snapshot(raw_yaml=config_yaml)

    # tmp-write + os.replace keeps readers from observing a partial file if the
    # process dies mid-write; matches trainer.py's checkpoint marker pattern.
    tmp_path = snapshot_path.with_suffix(".yaml.tmp")
    tmp_path.write_text(effective_yaml, encoding="utf-8")
    os.replace(tmp_path, snapshot_path)

    async with async_session_factory() as session:
        artifact = Artifact(
            id=str(uuid.uuid4()),
            run_id=run_id,
            project_id=project_id,
            artifact_type="config_snapshot",
            file_path=str(snapshot_path),
            file_size_bytes=snapshot_path.stat().st_size,
            is_retained=1,
            created_at=datetime.now(UTC).isoformat(),
        )
        session.add(artifact)
        await session.commit()


async def _process_trainer_event(
    *,
    event: dict[str, Any],
    run_id: str,
    project_id: str,
    stage_start_times: dict[str, str],
    final_metrics: dict[str, float],
) -> str:
    """Process one event from trainer stdout. Returns terminal status if complete, else ''."""
    event_type = event.get("type", "")
    timestamp = event.get("timestamp", datetime.now(UTC).isoformat())

    if event_type == "stage_enter":
        stage_name = event["stage_name"]
        stage_start_times[stage_name] = timestamp
        await _update_stage(
            run_id=run_id,
            stage_name=stage_name,
            status="running",
            started_at=timestamp,
        )
        await _update_run_status(
            run_id=run_id,
            status="running",
            current_stage=stage_name,
            started_at=timestamp,
        )
        await event_bus.publish(
            event_type=f"project.{project_id}.ws",
            payload={
                "channel": "run_state",
                "event": "stage_entered",
                "runId": run_id,
                "timestamp": timestamp,
                "payload": {
                    "runId": run_id,
                    "stageName": stage_name,
                    "stageOrder": event.get("stage_order", _STAGE_ORDER.get(stage_name, 0)),
                },
            },
        )

    elif event_type == "stage_complete":
        stage_name = event["stage_name"]
        duration_ms = event.get("duration_ms", 0)
        output_summary = event.get("output_summary", "")
        await _update_stage(
            run_id=run_id,
            stage_name=stage_name,
            status="completed",
            completed_at=timestamp,
            duration_ms=duration_ms,
            output_summary=output_summary,
        )
        await event_bus.publish(
            event_type=f"project.{project_id}.ws",
            payload={
                "channel": "run_state",
                "event": "stage_completed",
                "runId": run_id,
                "timestamp": timestamp,
                "payload": {
                    "runId": run_id,
                    "stageName": stage_name,
                    "durationMs": duration_ms,
                    "outputSummary": output_summary,
                },
            },
        )

    elif event_type == "stage_fail":
        stage_name = event["stage_name"]
        error = event.get("error", "unknown error")
        await _update_stage(
            run_id=run_id,
            stage_name=stage_name,
            status="failed",
            completed_at=timestamp,
            output_summary=error[:1000],
        )
        await event_bus.publish(
            event_type=f"project.{project_id}.ws",
            payload={
                "channel": "run_state",
                "event": "stage_failed",
                "runId": run_id,
                "timestamp": timestamp,
                "payload": {
                    "runId": run_id,
                    "stageName": stage_name,
                    "errorMessage": error,
                },
            },
        )

    elif event_type == "metric":
        step = event["step"]
        epoch = float(event.get("epoch", 0.0))
        metrics = event.get("metrics", {})
        final_metrics.update(metrics)
        await _record_metric_batch(run_id=run_id, step=step, epoch=epoch, metrics=metrics)
        await event_bus.publish(
            event_type=f"project.{project_id}.ws",
            payload={
                "channel": "metrics",
                "event": "metric_recorded",
                "runId": run_id,
                "timestamp": timestamp,
                "payload": {
                    "runId": run_id,
                    "step": step,
                    "epoch": epoch,
                    "metrics": metrics,
                },
            },
        )

    elif event_type == "progress":
        current_step = event.get("current_step", 0)
        total_steps = event.get("total_steps", 0)
        progress_pct = event.get("progress_pct", 0.0)
        epoch = float(event.get("epoch", 0.0))
        await _update_run_status(
            run_id=run_id,
            status="running",
            current_step=current_step,
            total_steps=total_steps,
            progress_pct=progress_pct,
        )
        await event_bus.publish(
            event_type=f"project.{project_id}.ws",
            payload={
                "channel": "run_state",
                "event": "progress_update",
                "runId": run_id,
                "timestamp": timestamp,
                "payload": {
                    "runId": run_id,
                    "currentStep": current_step,
                    "totalSteps": total_steps,
                    "progressPct": progress_pct,
                    "epoch": epoch,
                },
            },
        )

    elif event_type == "log":
        # log events are handled by the caller via log_buffer — nothing to emit here
        pass

    elif event_type == "checkpoint":
        step = event["step"]
        path = event["path"]
        size_bytes = event.get("size_bytes", 0)
        is_best_eval = bool(event.get("is_best_eval", False))
        await _update_run_status(run_id=run_id, status="running", last_checkpoint_path=path)
        await _record_artifact(
            run_id=run_id,
            project_id=project_id,
            artifact_type="checkpoint",
            file_path=path,
            size_bytes=size_bytes,
            is_best=1 if is_best_eval else 0,
        )
        async with async_session_factory() as session:
            retention_result = await apply_retention_after_checkpoint(
                session=session,
                run_id=run_id,
            )
        await event_bus.publish(
            event_type=f"project.{project_id}.ws",
            payload={
                "channel": "system",
                "event": "checkpoint_saved",
                "runId": run_id,
                "timestamp": timestamp,
                "payload": {
                    "runId": run_id,
                    "step": step,
                    "path": path,
                    "sizeBytes": size_bytes,
                    "isBestEval": is_best_eval,
                },
            },
        )
        await event_bus.publish(
            event_type=f"project.{project_id}.ws",
            payload={
                "channel": "system",
                "event": "retention_applied",
                "runId": run_id,
                "timestamp": timestamp,
                "payload": {
                    "runId": run_id,
                    "kept": retention_result["kept"],
                    "pruned": retention_result["pruned"],
                },
            },
        )

    elif event_type == "artifact":
        artifact_type = event.get("artifact_type", "model")
        path = event.get("path", "")
        size_bytes = event.get("size_bytes", 0)
        await _record_artifact(
            run_id=run_id,
            project_id=project_id,
            artifact_type=artifact_type,
            file_path=path,
            size_bytes=size_bytes,
        )
        await event_bus.publish(
            event_type=f"project.{project_id}.ws",
            payload={
                "channel": "system",
                "event": "artifact_created",
                "runId": run_id,
                "timestamp": timestamp,
                "payload": {"runId": run_id, "artifactType": artifact_type, "path": path},
            },
        )

    elif event_type == "model_profile":
        await _persist_model_profile(
            run_id=run_id,
            project_id=project_id,
            total_params=event["total_params"],
            trainable_params=event["trainable_params"],
            layers=event["layers"],
        )
        await event_bus.publish(
            event_type=f"project.{project_id}.ws",
            payload={
                "channel": "system",
                "event": "model_profile_ready",
                "runId": run_id,
                "timestamp": timestamp,
                "payload": {
                    "runId": run_id,
                    "layerCount": len(event["layers"]),
                    "totalParams": event["total_params"],
                    "trainableParams": event["trainable_params"],
                },
            },
        )

    elif event_type == "weight_stats":
        await _persist_weight_stats(
            run_id=run_id,
            step=event["step"],
            stats=event["stats"],
        )
        await event_bus.publish(
            event_type=f"project.{project_id}.ws",
            payload={
                "channel": "system",
                "event": "weight_stats_recorded",
                "runId": run_id,
                "timestamp": timestamp,
                "payload": {
                    "runId": run_id,
                    "step": event["step"],
                    "layerCount": len(event["stats"]),
                },
            },
        )

    elif event_type == "complete":
        return event.get("status", "completed")

    elif event_type == "error":
        # error log events are handled by the caller via log_buffer — nothing to emit here
        pass

    return ""


_LOG_BATCH_MAX = 50


def _append_log_line_to_disk(*, log_file_path: Path, entry: dict[str, str]) -> None:
    # JSON-lines file consumed by run_service.get_run_logs for historical/REST reads.
    # Best-effort: a disk write failure must not stop the training stream.
    try:
        with log_file_path.open("a", encoding="utf-8") as log_fh:
            log_fh.write(json.dumps(entry) + "\n")
    except OSError:
        logger.warning("failed to append log for run file %s", log_file_path, exc_info=True)


def _build_log_entry(*, event: dict[str, Any], severity: str) -> dict[str, str]:
    return {
        "severity": severity,
        "stage": event.get("stage", "") or "",
        "message": event.get("message", "") or "",
        "source": "trainer",
        "timestamp": event.get("timestamp", datetime.now(UTC).isoformat()),
    }


async def _flush_log_batch(
    *, run_id: str, project_id: str, log_buffer: list[dict[str, str]]
) -> None:
    if not log_buffer:
        return
    await event_bus.publish(
        event_type=f"project.{project_id}.ws",
        payload={
            "channel": "logs",
            "event": "log_batch",
            "runId": run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": {"runId": run_id, "lines": list(log_buffer)},
        },
    )
    log_buffer.clear()


async def _auto_analyze_if_enabled(*, run_id: str, project_id: str) -> None:
    try:
        async with async_session_factory() as session:
            run = await session.get(Run, run_id)
            if run is None:
                return
            config_version = await session.get(ConfigVersion, run.config_version_id)
            if config_version is None:
                return
            config: dict[str, Any] = yaml.safe_load(config_version.yaml_blob) or {}
            ai_cfg = config.get("ai_assistant", {})
            if not ai_cfg.get("auto_analyze_on_completion", True):
                return
            await suggestion_service.generate_suggestions(
                session=session,
                project_id=project_id,
                source_run_id=run_id,
            )
    except Exception:
        # Non-blocking: analysis failure must not affect run completion state
        logger.warning("Auto-analysis failed for run %s", run_id, exc_info=True)


async def _run_trainer_subprocess(
    *,
    run_id: str,
    project_id: str,
    config_path: Path,
    project_dir: Path,
    resume_from_checkpoint: str | None,
) -> None:
    await _update_run_status(run_id=run_id, status="running")

    log_dir = project_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir / f"{run_id}.log"

    # Read execution config up front so terminal cost accounting still works
    # even if the YAML on disk is later mutated by an unrelated edit.
    execution_cfg = _load_execution_config(config_path=config_path)

    try:
        proc = await dispatch_training(
            run_id=run_id,
            config_path=config_path,
            project_dir=project_dir,
            resume_from_checkpoint=resume_from_checkpoint,
        )
        _active_processes[run_id] = proc

        await _update_run_status(run_id=run_id, status="running", pid=proc.pid)

        stage_start_times: dict[str, str] = {}
        final_metrics: dict[str, float] = {}
        terminal_status = ""
        log_buffer: list[dict[str, str]] = []
        captured_failure_reason: str = ""
        captured_failure_stage: str = ""

        def _buffer_log(entry: dict[str, str]) -> None:
            log_buffer.append(entry)
            _append_log_line_to_disk(log_file_path=log_file_path, entry=entry)

        # Read stdout line by line
        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                event_type = event.get("type", "")
                if event_type == "log":
                    _buffer_log(
                        _build_log_entry(event=event, severity=event.get("severity", "info"))
                    )
                    if len(log_buffer) >= _LOG_BATCH_MAX:
                        await _flush_log_batch(
                            run_id=run_id, project_id=project_id, log_buffer=log_buffer
                        )
                elif event_type == "error":
                    captured_failure_reason = event.get("message", "unknown error")
                    captured_failure_stage = event.get("stage", captured_failure_stage)
                    _buffer_log(
                        {
                            "severity": "error",
                            "stage": event.get("stage", "unknown"),
                            "message": event.get("message", "unknown error"),
                            "source": "trainer",
                            "timestamp": event.get("timestamp", datetime.now(UTC).isoformat()),
                        }
                    )
                    if len(log_buffer) >= _LOG_BATCH_MAX:
                        await _flush_log_batch(
                            run_id=run_id, project_id=project_id, log_buffer=log_buffer
                        )
                else:
                    if event_type == "stage_fail":
                        captured_failure_stage = event.get("stage_name", captured_failure_stage)
                        captured_failure_reason = event.get("error", captured_failure_reason)
                    # Non-log event: flush pending log buffer before processing
                    await _flush_log_batch(
                        run_id=run_id, project_id=project_id, log_buffer=log_buffer
                    )
                    terminal_status = await _process_trainer_event(
                        event=event,
                        run_id=run_id,
                        project_id=project_id,
                        stage_start_times=stage_start_times,
                        final_metrics=final_metrics,
                    )
            except json.JSONDecodeError:
                # Non-JSON stdout (e.g., Python warnings) — persist as debug log
                _buffer_log(
                    {
                        "severity": "debug",
                        "stage": "",
                        "message": line,
                        "source": "trainer_stdout",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                if len(log_buffer) >= _LOG_BATCH_MAX:
                    await _flush_log_batch(
                        run_id=run_id, project_id=project_id, log_buffer=log_buffer
                    )

        # Flush any remaining log lines after stdout closes
        await _flush_log_batch(run_id=run_id, project_id=project_id, log_buffer=log_buffer)

        await proc.wait()
        removed = _active_processes.pop(run_id, None)
        if removed is not None:
            removed.cleanup()

        stderr_output = ""
        if proc.stderr is not None:
            stderr_bytes = await proc.stderr.read()
            stderr_output = stderr_bytes.decode("utf-8", errors="replace").strip()
            if stderr_output:
                logger.warning("Trainer stderr for run %s:\n%s", run_id, stderr_output)

        if not terminal_status:
            terminal_status = "completed" if proc.returncode == 0 else "failed"

        if terminal_status == "failed" and not captured_failure_reason:
            if stderr_output:
                captured_failure_reason = stderr_output[-2000:]
            else:
                captured_failure_reason = f"Trainer process exited with code {proc.returncode}"

        now = datetime.now(UTC).isoformat()
        started_iso = await _load_run_started_iso(run_id=run_id)
        wall_clock_s, cost_usd = (0.0, 0.0)
        if started_iso is not None:
            wall_clock_s, cost_usd = _compute_run_cost(
                execution=execution_cfg,
                started_iso=started_iso,
                ended_iso=now,
            )

        if terminal_status == "completed":
            await _mark_pending_stages_skipped(run_id=run_id)
            await _update_run_status(
                run_id=run_id,
                status="completed",
                cost_usd=cost_usd,
                wall_clock_s=wall_clock_s,
            )
            async with async_session_factory() as session:
                await _run_final_retention_sweep(session=session, project_id=project_id)
            await event_bus.publish(
                event_type=f"project.{project_id}.ws",
                payload={
                    "channel": "run_state",
                    "event": "run_completed",
                    "runId": run_id,
                    "timestamp": now,
                    "payload": {
                        "runId": run_id,
                        "totalDurationMs": 0,
                        "finalMetrics": final_metrics,
                        "costUsd": cost_usd,
                        "wallClockS": wall_clock_s,
                    },
                },
            )
            analysis_task = asyncio.create_task(
                _auto_analyze_if_enabled(run_id=run_id, project_id=project_id),
                name=f"auto-analyze-{run_id}",
            )
            _active_analysis_tasks.add(analysis_task)
            analysis_task.add_done_callback(_active_analysis_tasks.discard)
            analysis_task.add_done_callback(_log_background_task_exception)
        elif terminal_status == "cancelled":
            await _mark_pending_stages_skipped(run_id=run_id)
            await _update_run_status(
                run_id=run_id,
                status="cancelled",
                cost_usd=cost_usd,
                wall_clock_s=wall_clock_s,
            )
            async with async_session_factory() as session:
                await _run_final_retention_sweep(session=session, project_id=project_id)
            await event_bus.publish(
                event_type=f"project.{project_id}.ws",
                payload={
                    "channel": "run_state",
                    "event": "run_cancelled",
                    "runId": run_id,
                    "timestamp": now,
                    "payload": {
                        "runId": run_id,
                        "costUsd": cost_usd,
                        "wallClockS": wall_clock_s,
                    },
                },
            )
        else:
            await _mark_pending_stages_skipped(run_id=run_id)
            await _update_run_status(
                run_id=run_id,
                status="failed",
                failure_reason=captured_failure_reason,
                failure_stage=captured_failure_stage or None,
                cost_usd=cost_usd,
                wall_clock_s=wall_clock_s,
            )
            async with async_session_factory() as session:
                await _run_final_retention_sweep(session=session, project_id=project_id)
            await event_bus.publish(
                event_type=f"project.{project_id}.ws",
                payload={
                    "channel": "run_state",
                    "event": "run_failed",
                    "runId": run_id,
                    "timestamp": now,
                    "payload": {
                        "runId": run_id,
                        "failureReason": captured_failure_reason,
                        "failureStage": captured_failure_stage or None,
                        "lastStep": 0,
                        "costUsd": cost_usd,
                        "wallClockS": wall_clock_s,
                    },
                },
            )

    except Exception as exc:
        removed = _active_processes.pop(run_id, None)
        if removed is not None:
            removed.cleanup()
        await _update_run_status(
            run_id=run_id,
            status="failed",
            failure_reason=str(exc),
        )
        async with async_session_factory() as session:
            await _run_final_retention_sweep(session=session, project_id=project_id)


async def cancel_run(*, session: AsyncSession, run_id: str) -> Run:
    run = await get_run(session=session, run_id=run_id)
    if run.status not in ("pending", "running"):
        raise ValueError(f"Run {run_id} is not cancellable in status {run.status}")

    proc = _active_processes.get(run_id)
    if proc is not None:
        proc.terminate()

    await _mark_pending_stages_skipped(run_id=run_id)

    now = datetime.now(UTC).isoformat()
    run.status = "cancelled"
    run.completed_at = now
    run.updated_at = now
    await session.commit()
    await session.refresh(run)
    return run


async def pause_run(*, session: AsyncSession, run_id: str) -> Run:
    run = await get_run(session=session, run_id=run_id)
    if run.status != "running":
        raise ValueError(f"Run {run_id} is not pausable in status {run.status}")

    proc = _active_processes.get(run_id)
    if proc is not None:
        if _IS_UNIX:
            proc.send_signal(_signal.SIGSTOP)
        else:
            import psutil

            with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                psutil.Process(proc.pid).suspend()

    now = datetime.now(UTC).isoformat()
    run.status = "paused"
    run.updated_at = now
    await session.commit()
    await session.refresh(run)

    await event_bus.publish(
        event_type=f"project.{run.project_id}.ws",
        payload={
            "channel": "run_state",
            "event": "run_paused",
            "runId": run_id,
            "timestamp": now,
            "payload": {"runId": run_id, "pausedAtStep": run.current_step},
        },
    )
    return run


async def resume_run(*, session: AsyncSession, project_id: str, run_id: str) -> Run:
    """Create a new child run that resumes from the last checkpoint."""
    parent_run = await get_run(session=session, run_id=run_id)
    if parent_run.status not in ("failed", "cancelled", "paused", "completed"):
        raise ValueError(f"Run {run_id} cannot be resumed from status {parent_run.status}")

    # If paused and process still alive, just resume it
    proc = _active_processes.get(run_id)
    if parent_run.status == "paused" and proc is not None:
        if _IS_UNIX:
            try:
                proc.send_signal(_signal.SIGCONT)
            except (ProcessLookupError, OSError):
                pass
            else:
                now = datetime.now(UTC).isoformat()
                parent_run.status = "running"
                parent_run.updated_at = now
                await session.commit()
                await session.refresh(parent_run)
                return parent_run
        else:
            import psutil

            try:
                psutil.Process(proc.pid).resume()
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                pass
            else:
                now = datetime.now(UTC).isoformat()
                parent_run.status = "running"
                parent_run.updated_at = now
                await session.commit()
                await session.refresh(parent_run)
                return parent_run

    child_payload = RunCreate(
        config_version_id=parent_run.config_version_id,
        parent_run_id=run_id,
    )
    return await create_run(session=session, project_id=project_id, payload=child_payload)
