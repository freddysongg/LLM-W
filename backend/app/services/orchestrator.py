from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal as _signal
import sys
import uuid
from datetime import UTC, datetime, timedelta
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
    RunNotFoundError,
    RunStateError,
)
from app.core.modal_catalog import (
    MODAL_GPU_CATALOG,
    get_modal_gpu_option,
    get_modal_gpu_rate_usd_per_second,
)
from app.models.artifact import Artifact
from app.models.config_version import ConfigVersion
from app.models.metric_point import MetricPoint
from app.models.model_profile import ModelProfile
from app.models.project import Project
from app.models.run import Run
from app.models.run_attempt import RunAttempt
from app.models.run_stage import RunStage
from app.models.weight_snapshot import WeightSnapshot
from app.schemas.run import RunCreate, RunResponse
from app.schemas.workbench_config import ExecutionConfig
from app.services import settings_service, suggestion_service
from app.services.config_service import serialize_config_yaml_snapshot
from app.services.oom_detector import detect_oom
from app.services.storage_manager import (
    apply_retention_after_checkpoint,
    run_project_cleanup,
)
from app.services.training_dispatcher import (
    TrainingProcess,
    UnsupportedEnvironmentError,
    dispatch_training,
)

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


def _evict_completed_trainer_task(*, run_id: str, completed: asyncio.Task[None]) -> None:
    """Drop the trainer task handle iff it is still the registered one.

    An OOM auto-fallback respawns the trainer under the same `run_id` while
    the prior task is still in flight. When the prior task finishes, its
    `add_done_callback` must not blindly evict whatever sits in `_active_tasks`
    — the identity check below guarantees only the matching task is removed.
    """
    if _active_tasks.get(run_id) is completed:
        _active_tasks.pop(run_id, None)


async def list_runs(*, session: AsyncSession, project_id: str) -> list[Run]:
    result = await session.execute(
        select(Run).where(Run.project_id == project_id).order_by(Run.created_at.desc())
    )
    return list(result.scalars().all())


async def get_run(*, session: AsyncSession, run_id: str) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise RunNotFoundError(run_id)
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

    # Seed attempt index 0 — the OOM-fallback machinery uses this row as the
    # cost-window anchor for the run's first try. Subsequent attempts are added
    # via accept_fallback when the user (or auto strategy) picks a larger GPU.
    initial_attempt = RunAttempt(
        id=str(uuid.uuid4()),
        run_id=run_id,
        attempt_index=0,
        gpu_type=(
            execution_cfg.modal_gpu_type if execution_cfg.environment == "modal" else None
        ),
        device=execution_cfg.device,
        started_at=now,
        created_at=now,
    )
    session.add(initial_attempt)

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
        _evict_completed_trainer_task(run_id=run_id, completed=completed)
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

    if execution.max_estimated_cost_usd > settings.max_allowed_cost_usd:
        raise UnsupportedEnvironmentError(
            f"execution.max_estimated_cost_usd ({execution.max_estimated_cost_usd}) "
            f"exceeds the hard cap of ${settings.max_allowed_cost_usd}. Lower the budget or "
            "raise the cap explicitly."
        )

    # The user-supplied budget is a self-report; the actual ceiling is GPU rate ×
    # sandbox timeout, since the sandbox can run for the full `max_run_minutes`
    # window regardless of what the user estimated. Reject when that ceiling
    # exceeds the cap so a slow H100 config can't outspend the budget.
    _enforce_worst_case_cost_cap(
        gpu_type=execution.modal_gpu_type,
        max_run_minutes=execution.max_run_minutes,
    )

    if settings_service.get_modal_credentials() is None:
        raise UnsupportedEnvironmentError(
            "Modal training requires modal_token_id and modal_token_secret to be "
            "configured under workbench settings before launching a cloud run."
        )


def _enforce_worst_case_cost_cap(*, gpu_type: str, max_run_minutes: int) -> None:
    """Reject GPU + timeout pairs whose worst-case spend exceeds the hard cap.

    Used by the launch-time validator and the OOM-fallback accept path: both
    must hold the same ceiling so the user can't escape the budget by retrying
    on a pricier card.
    """
    gpu_rate = get_modal_gpu_rate_usd_per_second(gpu_type=gpu_type)
    worst_case_cost_usd = max_run_minutes * 60 * gpu_rate
    if worst_case_cost_usd > settings.max_allowed_cost_usd:
        raise UnsupportedEnvironmentError(
            f"Worst-case spend for modal_gpu_type='{gpu_type}' over "
            f"max_run_minutes={max_run_minutes} is "
            f"${worst_case_cost_usd:.2f}, which exceeds the hard cap of "
            f"${settings.max_allowed_cost_usd}. Lower max_run_minutes or choose a cheaper GPU."
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
    rate = get_modal_gpu_rate_usd_per_second(gpu_type=execution.modal_gpu_type)
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
    gpu_type_override: str | None = None,
) -> None:
    await _update_run_status(run_id=run_id, status="running")

    log_dir = project_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir / f"{run_id}.log"

    # Read execution config up front so terminal cost accounting still works
    # even if the YAML on disk is later mutated by an unrelated edit. On a
    # fallback respawn the on-disk YAML still names the original GPU; an
    # override here keeps the persisted cost and downstream dispatch in sync
    # with the GPU the operator actually accepted.
    execution_cfg = _load_execution_config(config_path=config_path)
    if gpu_type_override is not None:
        execution_cfg = execution_cfg.model_copy(update={"modal_gpu_type": gpu_type_override})

    try:
        proc = await dispatch_training(
            run_id=run_id,
            config_path=config_path,
            project_dir=project_dir,
            resume_from_checkpoint=resume_from_checkpoint,
            gpu_type_override=gpu_type_override,
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

        proc_exit_code = proc.returncode if proc.returncode is not None else -1
        modal_stderr_tail, modal_exception_type = _extract_modal_failure_details(proc=proc)
        effective_stderr_tail = modal_stderr_tail or stderr_output

        now = datetime.now(UTC).isoformat()
        started_iso = await _load_run_started_iso(run_id=run_id)
        wall_clock_s = 0.0
        if started_iso is not None:
            wall_clock_s, _ = _compute_run_cost(
                execution=execution_cfg,
                started_iso=started_iso,
                ended_iso=now,
            )

        if terminal_status == "completed":
            # Close the current attempt FIRST so its cost lands in run_attempts,
            # then read the rolling total across all attempts. Without this,
            # `Run.cost_usd` would drop the cost of any failed fallback attempt.
            await _close_current_attempt(
                run_id=run_id, execution=execution_cfg, exit_reason="completed"
            )
            cost_usd = await _sum_attempt_costs(run_id=run_id)
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
            await _close_current_attempt(
                run_id=run_id, execution=execution_cfg, exit_reason="cancelled"
            )
            cost_usd = await _sum_attempt_costs(run_id=run_id)
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
            handled_by_fallback = await _handle_trainer_oom(
                run_id=run_id,
                project_id=project_id,
                execution=execution_cfg,
                exit_code=proc_exit_code,
                stderr_tail=effective_stderr_tail,
                exception_type_name=modal_exception_type,
            )
            if handled_by_fallback:
                # OOM fallback owns the terminal state from here — either it
                # transitioned the run to fallback_pending and emitted a WS
                # event, or it failed the run with oom_chain_exhausted itself.
                return
            await _close_current_attempt(
                run_id=run_id, execution=execution_cfg, exit_reason="failed"
            )
            cost_usd = await _sum_attempt_costs(run_id=run_id)
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


def _extract_modal_failure_details(*, proc: object) -> tuple[str, str | None]:
    """Pull (stderr_tail, exception_type_name) off a Modal-backed TrainingProcess.

    Returns empty/None for local subprocesses or any handle that doesn't expose
    the Modal-specific attributes — the existing stderr capture above already
    covers those paths.
    """
    adapter = getattr(proc, "adapter", None)
    if adapter is None:
        return ("", None)
    stderr_tail_attr = getattr(adapter, "last_stderr_tail", "")
    exception_type_attr = getattr(adapter, "last_exception_type_name", None)
    stderr_tail = stderr_tail_attr if isinstance(stderr_tail_attr, str) else ""
    exception_type = exception_type_attr if isinstance(exception_type_attr, str) else None
    return (stderr_tail, exception_type)


def _load_fallback_settings(*, execution: ExecutionConfig) -> tuple[list[str], str]:
    fallback = execution.modal_oom_fallback
    chain_str: list[str] = list(fallback.chain)
    return (chain_str, fallback.strategy)


def _filter_fallback_candidates(
    *,
    chain: list[str],
    max_run_minutes: int,
    exclude_gpu_type: str | None,
) -> list[object]:
    """Return GPU options from the fallback chain that pass cost-cap + de-dup checks.

    `exclude_gpu_type` is the currently-failed GPU; we never recommend the same
    GPU as the next attempt. Unknown GPU types in the chain are silently dropped
    (the Pydantic Literal would reject typos at config load time anyway).
    """
    candidates: list[object] = []
    for gpu_type in chain:
        if exclude_gpu_type is not None and gpu_type == exclude_gpu_type:
            continue
        option = get_modal_gpu_option(gpu_type=gpu_type)
        if option is None:
            continue
        worst_case = max_run_minutes * 60 * (option.rate_usd_hr / 3600.0)
        if worst_case > settings.max_allowed_cost_usd:
            continue
        candidates.append(option)
    return candidates


def _serialize_gpu_option(*, option: object) -> dict[str, Any]:
    return {
        "gpu_type": getattr(option, "gpu_type", ""),
        "label": getattr(option, "label", ""),
        "vram_gb": getattr(option, "vram_gb", 0),
        "rate_usd_hr": getattr(option, "rate_usd_hr", 0.0),
    }


async def _load_current_attempt(*, session: AsyncSession, run_id: str) -> RunAttempt | None:
    """Return the highest-indexed attempt for a run (its current attempt)."""
    result = await session.execute(
        select(RunAttempt)
        .where(RunAttempt.run_id == run_id)
        .order_by(RunAttempt.attempt_index.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _close_attempt_with_reason(
    *,
    session: AsyncSession,
    attempt: RunAttempt,
    execution: ExecutionConfig,
    exit_reason: str,
) -> None:
    now = datetime.now(UTC).isoformat()
    attempt.ended_at = now
    attempt.exit_reason = exit_reason
    started = datetime.fromisoformat(attempt.started_at)
    ended = datetime.fromisoformat(now)
    wall_clock_s = max(0.0, (ended - started).total_seconds())
    if execution.environment == "modal" and attempt.gpu_type is not None:
        rate = get_modal_gpu_rate_usd_per_second(gpu_type=attempt.gpu_type)
        attempt.cost_estimate_usd = wall_clock_s * rate
    else:
        attempt.cost_estimate_usd = 0.0


async def _sum_attempt_costs(*, run_id: str) -> float:
    """Return total cost across all RunAttempt rows for a run.

    Used at run completion to make `Run.cost_usd` a rolling total over attempts
    — failed fallback attempts already have `cost_estimate_usd` persisted, and
    the current attempt is closed (and priced) right before this is called.
    """
    async with async_session_factory() as session:
        result = await session.execute(
            select(RunAttempt.cost_estimate_usd).where(RunAttempt.run_id == run_id)
        )
        return sum((cost or 0.0) for cost in result.scalars().all())


async def _close_current_attempt(
    *, run_id: str, execution: ExecutionConfig, exit_reason: str
) -> None:
    """Mark the current attempt closed with the given reason if not already closed."""
    async with async_session_factory() as session:
        attempt = await _load_current_attempt(session=session, run_id=run_id)
        if attempt is None or attempt.ended_at is not None:
            return
        await _close_attempt_with_reason(
            session=session, attempt=attempt, execution=execution, exit_reason=exit_reason
        )
        await session.commit()


async def _publish_local_oom_detected(
    *,
    run_id: str,
    project_id: str,
    device: str,
    exit_code: int,
    detected_via: str | None,
) -> None:
    await event_bus.publish(
        event_type=f"project.{project_id}.ws",
        payload={
            "channel": "system",
            "event": "oom_detected",
            "runId": run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": {
                "run_id": run_id,
                "device": device,
                "exit_code": exit_code,
                "detected_via": detected_via,
            },
        },
    )


async def _fail_run_with_oom_reason(
    *,
    run_id: str,
    project_id: str,
    failure_reason: str,
    publish_run_failed: bool,
) -> None:
    await _mark_pending_stages_skipped(run_id=run_id)
    await _update_run_status(
        run_id=run_id,
        status="failed",
        failure_reason=failure_reason,
        failure_stage=None,
    )
    async with async_session_factory() as session:
        await _run_final_retention_sweep(session=session, project_id=project_id)
    if publish_run_failed:
        await event_bus.publish(
            event_type=f"project.{project_id}.ws",
            payload={
                "channel": "run_state",
                "event": "run_failed",
                "runId": run_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "payload": {
                    "runId": run_id,
                    "failureReason": failure_reason,
                    "failureStage": None,
                    "lastStep": 0,
                    "costUsd": 0.0,
                    "wallClockS": 0.0,
                },
            },
        )


async def _close_failed_attempt(*, run_id: str, execution: ExecutionConfig) -> RunAttempt | None:
    async with async_session_factory() as session:
        attempt = await _load_current_attempt(session=session, run_id=run_id)
        if attempt is not None:
            await _close_attempt_with_reason(
                session=session,
                attempt=attempt,
                execution=execution,
                exit_reason="oom",
            )
        await session.commit()
    return attempt


async def _transition_to_fallback_pending(*, run_id: str) -> bool:
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return False
        run.status = "fallback_pending"
        run.updated_at = datetime.now(UTC).isoformat()
        await session.commit()
    return True


async def _auto_accept_first_candidate(
    *, run_id: str, project_id: str, gpu_type: str
) -> None:
    if not await _transition_to_fallback_pending(run_id=run_id):
        return
    async with async_session_factory() as session:
        await accept_fallback(
            session=session, run_id=run_id, project_id=project_id, gpu_type=gpu_type
        )


async def _publish_fallback_proposed(
    *,
    run_id: str,
    project_id: str,
    execution: ExecutionConfig,
    attempt: RunAttempt | None,
    candidates: list[object],
    detected_via: str | None,
) -> None:
    await event_bus.publish(
        event_type=f"project.{project_id}.ws",
        payload={
            "channel": "run_state",
            "event": "fallback_proposed",
            "runId": run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": {
                "run_id": run_id,
                "attempt_index": attempt.attempt_index if attempt is not None else 0,
                "from_gpu": execution.modal_gpu_type,
                "candidates": [_serialize_gpu_option(option=opt) for opt in candidates],
                "detected_via": detected_via,
                "preserved_volume": True,
            },
        },
    )


async def _handle_trainer_oom(
    *,
    run_id: str,
    project_id: str,
    execution: ExecutionConfig,
    exit_code: int,
    stderr_tail: str,
    exception_type_name: str | None,
) -> bool:
    """Classify a trainer failure and trigger the fallback flow when applicable.

    Returns True if the failure was identified as OOM and consumed by the
    fallback machinery (either by transitioning to fallback_pending, auto-
    accepting the next GPU, or terminating the run with chain_exhausted). When
    it returns False the caller continues down the existing generic-failure
    path with no state changes.
    """
    device = execution.device if execution.environment != "modal" else "modal"
    detection = detect_oom(
        device=device,
        exit_code=exit_code,
        stderr_tail=stderr_tail,
        exception_type_name=exception_type_name,
    )
    if not detection.is_oom:
        return False

    if execution.environment != "modal":
        # Local OOM detection is observation-only per spec — there is no
        # fallback chain on the host. Emit a system-channel event so the UI
        # can surface a toast, then return False to let the generic failure
        # path mark the run failed.
        await _publish_local_oom_detected(
            run_id=run_id,
            project_id=project_id,
            device=device,
            exit_code=exit_code,
            detected_via=detection.trigger,
        )
        return False

    chain, strategy = _load_fallback_settings(execution=execution)
    attempt = await _close_failed_attempt(run_id=run_id, execution=execution)

    if strategy == "disabled":
        # Disabled strategy is still a terminal failure — the WS clients need
        # the `run_failed` envelope so the UI stops showing the run as active.
        # The original False here also forced the caller's generic publisher
        # to skip, leaving clients without any failure notification.
        await _fail_run_with_oom_reason(
            run_id=run_id,
            project_id=project_id,
            failure_reason="oom",
            publish_run_failed=True,
        )
        return True

    candidates = _filter_fallback_candidates(
        chain=chain,
        max_run_minutes=execution.max_run_minutes,
        exclude_gpu_type=execution.modal_gpu_type,
    )
    if not candidates:
        await _fail_run_with_oom_reason(
            run_id=run_id,
            project_id=project_id,
            failure_reason="oom_chain_exhausted",
            publish_run_failed=True,
        )
        return True

    if strategy == "auto":
        chosen = candidates[0]
        await _auto_accept_first_candidate(
            run_id=run_id,
            project_id=project_id,
            gpu_type=str(getattr(chosen, "gpu_type", "")),
        )
        return True

    # strategy == "ask": surface candidates and pause the run.
    if not await _transition_to_fallback_pending(run_id=run_id):
        return True
    await _publish_fallback_proposed(
        run_id=run_id,
        project_id=project_id,
        execution=execution,
        attempt=attempt,
        candidates=candidates,
        detected_via=detection.trigger,
    )
    return True


async def _sweep_abandoned_fallback_runs() -> None:
    """Auto-fail fallback_pending runs idle past the configured TTL.

    Without this sweep, a client that closes the browser between
    `fallback_proposed` and `accept_fallback` leaves the run stuck in
    `fallback_pending` until the process is restarted. Each row is processed
    inside its own try/except so a malformed run cannot break startup.
    """
    cutoff_iso = (
        datetime.now(UTC) - timedelta(hours=settings.oom_fallback_recovery_ttl_hours)
    ).isoformat()
    async with async_session_factory() as session:
        result = await session.execute(
            select(Run).where(
                Run.status == "fallback_pending",
                Run.updated_at < cutoff_iso,
            )
        )
        stale_runs = list(result.scalars().all())

    for run in stale_runs:
        try:
            await _fail_abandoned_fallback_run(run_id=run.id, project_id=run.project_id)
        except Exception:
            logger.exception(
                "orchestrator sweep failed to fail-out abandoned fallback run %s", run.id
            )


async def _fail_abandoned_fallback_run(*, run_id: str, project_id: str) -> None:
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        config_version = await session.get(ConfigVersion, run.config_version_id)
        if config_version is None:
            execution_cfg = ExecutionConfig.model_validate(
                {"environment": run.environment or "modal"}
            )
        else:
            execution_cfg = _load_execution_cfg_from_config_version(
                config_version=config_version
            )
        attempt = await _load_current_attempt(session=session, run_id=run_id)
        if attempt is not None and attempt.ended_at is None:
            await _close_attempt_with_reason(
                session=session,
                attempt=attempt,
                execution=execution_cfg,
                exit_reason="oom_fallback_abandoned",
            )
            await session.commit()

    await _fail_run_with_oom_reason(
        run_id=run_id,
        project_id=project_id,
        failure_reason="oom_fallback_abandoned",
        publish_run_failed=True,
    )


def _validate_fallback_gpu_choice(*, run: Run, gpu_type: str, max_run_minutes: int) -> None:
    if not any(option.gpu_type == gpu_type for option in MODAL_GPU_CATALOG):
        raise UnsupportedEnvironmentError(
            f"Unsupported Modal GPU type for fallback: '{gpu_type}'. "
            f"Expected one of: {', '.join(option.gpu_type for option in MODAL_GPU_CATALOG)}."
        )
    if gpu_type == run.modal_gpu_type:
        raise UnsupportedEnvironmentError(
            f"Fallback GPU '{gpu_type}' is the same as the GPU that just OOM'd. "
            "Pick a different option from the proposed candidates."
        )
    _enforce_worst_case_cost_cap(gpu_type=gpu_type, max_run_minutes=max_run_minutes)


async def _next_attempt_index(*, session: AsyncSession, run_id: str) -> int:
    result = await session.execute(
        select(RunAttempt.attempt_index)
        .where(RunAttempt.run_id == run_id)
        .order_by(RunAttempt.attempt_index.desc())
        .limit(1)
    )
    current = result.scalar_one_or_none()
    return 0 if current is None else current + 1


def _load_execution_cfg_from_config_version(*, config_version: ConfigVersion) -> ExecutionConfig:
    raw_config: dict[str, object] = yaml.safe_load(config_version.yaml_blob) or {}
    execution_raw = raw_config.get("execution", {})
    return ExecutionConfig.model_validate(
        execution_raw if isinstance(execution_raw, dict) else {}
    )


def _spawn_trainer_task(
    *,
    run_id: str,
    project_id: str,
    config_path: Path,
    project_dir: Path,
    resume_from_checkpoint: str | None,
    task_name: str,
    gpu_type_override: str | None = None,
) -> None:
    task = asyncio.create_task(
        _run_trainer_subprocess(
            run_id=run_id,
            project_id=project_id,
            config_path=config_path,
            project_dir=project_dir,
            resume_from_checkpoint=resume_from_checkpoint,
            gpu_type_override=gpu_type_override,
        ),
        name=task_name,
    )
    _active_tasks[run_id] = task

    def _on_task_done(completed: asyncio.Task[None]) -> None:
        _evict_completed_trainer_task(run_id=run_id, completed=completed)
        _log_background_task_exception(completed)

    task.add_done_callback(_on_task_done)


async def accept_fallback(
    *,
    session: AsyncSession,
    run_id: str,
    project_id: str,
    gpu_type: str,
) -> Run:
    """Promote a fallback_pending run to running with a new GPU choice.

    Re-runs the cost-cap gate against the new GPU so the operator cannot escape
    the budget by retrying on a pricier card. Spawns the trainer subprocess
    again via the same orchestration task path as create_run.
    """
    run = await get_run(session=session, run_id=run_id)
    if run.project_id != project_id:
        # Treat cross-project access as a 404 so the route does not leak the
        # existence of runs in other projects.
        raise RunNotFoundError(run_id)
    if run.status != "fallback_pending":
        raise RunStateError(run_id=run_id, action="accept_fallback", current_status=run.status)

    config_version = await session.get(ConfigVersion, run.config_version_id)
    if config_version is None:
        raise ConfigVersionNotFoundError(run.config_version_id)
    execution_cfg = _load_execution_cfg_from_config_version(config_version=config_version)

    _validate_fallback_gpu_choice(
        run=run,
        gpu_type=gpu_type,
        max_run_minutes=execution_cfg.max_run_minutes,
    )

    project = await session.get(Project, run.project_id)
    if project is None:
        raise ProjectNotFoundError(run.project_id)

    now = datetime.now(UTC).isoformat()
    next_index = await _next_attempt_index(session=session, run_id=run_id)
    session.add(
        RunAttempt(
            id=str(uuid.uuid4()),
            run_id=run_id,
            attempt_index=next_index,
            gpu_type=gpu_type,
            device=run.environment,
            started_at=now,
            created_at=now,
        )
    )

    run.modal_gpu_type = gpu_type
    run.status = "running"
    run.updated_at = now
    # Reset the run-level cost anchor so the next attempt's `stage_enter` write
    # of `started_at` represents the new attempt's window, not the failed first
    # attempt's. Cost is reported per-attempt via RunAttempt.cost_estimate_usd;
    # Run.cost_usd is the rolling total across attempts.
    run.started_at = None
    await session.commit()

    project_dir = Path(project.directory_path)
    config_path = _resolve_config_path(config_version=config_version, project_dir=project_dir)
    _spawn_trainer_task(
        run_id=run_id,
        project_id=run.project_id,
        config_path=config_path,
        project_dir=project_dir,
        resume_from_checkpoint=run.last_checkpoint_path,
        task_name=f"trainer-fallback-{run_id}",
        gpu_type_override=gpu_type,
    )

    await session.refresh(run)
    return run


async def cancel_fallback(*, session: AsyncSession, run_id: str, project_id: str) -> Run:
    """Abort a fallback_pending run when the user declines further retries."""
    run = await get_run(session=session, run_id=run_id)
    if run.project_id != project_id:
        raise RunNotFoundError(run_id)
    if run.status != "fallback_pending":
        raise RunStateError(run_id=run_id, action="cancel_fallback", current_status=run.status)

    config_version = await session.get(ConfigVersion, run.config_version_id)
    if config_version is None:
        raise ConfigVersionNotFoundError(run.config_version_id)

    execution_cfg = _load_execution_cfg_from_config_version(config_version=config_version)

    attempt = await _load_current_attempt(session=session, run_id=run_id)
    if attempt is not None and attempt.ended_at is None:
        await _close_attempt_with_reason(
            session=session,
            attempt=attempt,
            execution=execution_cfg,
            exit_reason="oom_user_cancelled",
        )

    now = datetime.now(UTC).isoformat()
    run.status = "failed"
    run.failure_reason = "oom_user_cancelled"
    run.completed_at = now
    run.updated_at = now
    await session.commit()

    await _mark_pending_stages_skipped(run_id=run_id)

    await session.refresh(run)

    await event_bus.publish(
        event_type=f"project.{run.project_id}.ws",
        payload={
            "channel": "run_state",
            "event": "run_failed",
            "runId": run_id,
            "timestamp": now,
            "payload": {
                "runId": run_id,
                "failureReason": "oom_user_cancelled",
                "failureStage": None,
                "lastStep": run.current_step,
                "costUsd": run.cost_usd,
                "wallClockS": run.wall_clock_s,
            },
        },
    )

    return run


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
