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
from app.models.project import Project
from app.models.run import Run
from app.models.run_stage import RunStage
from app.schemas.run import RunCreate, RunResponse
from app.services import suggestion_service

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

# Maps run_id → asyncio.subprocess.Process
_active_processes: dict[str, asyncio.subprocess.Process] = {}


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
            },
        },
    )

    # Launch trainer subprocess asynchronously
    resume_checkpoint: str | None = None
    if payload.parent_run_id:
        parent = await session.get(Run, payload.parent_run_id)
        if parent is not None and parent.last_checkpoint_path:
            resume_checkpoint = parent.last_checkpoint_path

    config_path = _resolve_config_path(
        config_version=config_version, project_dir=settings.projects_dir / project.name
    )
    project_dir = settings.projects_dir / project.name

    asyncio.create_task(
        _run_trainer_subprocess(
            run_id=run_id,
            project_id=project_id,
            config_path=config_path,
            project_dir=project_dir,
            resume_from_checkpoint=resume_checkpoint,
        )
    )

    return run


def _resolve_config_path(*, config_version: ConfigVersion, project_dir: Path) -> Path:
    config_path = project_dir / "configs" / f"version-{config_version.version_number}.yaml"
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_version.yaml_blob)
    return config_path


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
        await session.commit()


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
    *, run_id: str, project_id: str, artifact_type: str, file_path: str, size_bytes: int
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
            created_at=now,
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
        await _update_run_status(run_id=run_id, status="running", last_checkpoint_path=path)
        await _record_artifact(
            run_id=run_id,
            project_id=project_id,
            artifact_type="checkpoint",
            file_path=path,
            size_bytes=size_bytes,
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

    elif event_type == "complete":
        return event.get("status", "completed")

    elif event_type == "error":
        # error log events are handled by the caller via log_buffer — nothing to emit here
        pass

    return ""


_LOG_BATCH_MAX = 50


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
    cmd = [
        sys.executable,
        "-u",
        "-m",
        "app.services.trainer",
        "--run-id",
        run_id,
        "--config-path",
        str(config_path),
        "--project-dir",
        str(project_dir),
        "--heartbeat-interval",
        str(settings.watchdog_heartbeat_interval_seconds),
    ]
    if resume_from_checkpoint:
        cmd += ["--resume-from-checkpoint", resume_from_checkpoint]

    await _update_run_status(run_id=run_id, status="running")

    try:
        subprocess_env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(__file__).parent.parent.parent),
            env=subprocess_env,
        )
        _active_processes[run_id] = proc

        await _update_run_status(run_id=run_id, status="running", pid=proc.pid)

        stage_start_times: dict[str, str] = {}
        final_metrics: dict[str, float] = {}
        terminal_status = ""
        log_buffer: list[dict[str, str]] = []
        captured_failure_reason: str = ""
        captured_failure_stage: str = ""

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
                    log_buffer.append(
                        {
                            "severity": event.get("severity", "info"),
                            "stage": event.get("stage", ""),
                            "message": event.get("message", ""),
                            "source": "trainer",
                        }
                    )
                    if len(log_buffer) >= _LOG_BATCH_MAX:
                        await _flush_log_batch(
                            run_id=run_id, project_id=project_id, log_buffer=log_buffer
                        )
                elif event_type == "error":
                    captured_failure_reason = event.get("message", "unknown error")
                    captured_failure_stage = event.get("stage", captured_failure_stage)
                    log_buffer.append(
                        {
                            "severity": "error",
                            "stage": event.get("stage", "unknown"),
                            "message": event.get("message", "unknown error"),
                            "source": "trainer",
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
                # Non-JSON stdout (e.g., Python warnings) — buffer as debug log
                log_buffer.append(
                    {
                        "severity": "debug",
                        "stage": "",
                        "message": line,
                        "source": "trainer_stdout",
                    }
                )
                if len(log_buffer) >= _LOG_BATCH_MAX:
                    await _flush_log_batch(
                        run_id=run_id, project_id=project_id, log_buffer=log_buffer
                    )

        # Flush any remaining log lines after stdout closes
        await _flush_log_batch(run_id=run_id, project_id=project_id, log_buffer=log_buffer)

        await proc.wait()
        _active_processes.pop(run_id, None)

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
        if terminal_status == "completed":
            await _mark_pending_stages_skipped(run_id=run_id)
            await _update_run_status(run_id=run_id, status="completed")
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
                    },
                },
            )
            asyncio.create_task(_auto_analyze_if_enabled(run_id=run_id, project_id=project_id))
        elif terminal_status == "cancelled":
            await _mark_pending_stages_skipped(run_id=run_id)
            await _update_run_status(run_id=run_id, status="cancelled")
            await event_bus.publish(
                event_type=f"project.{project_id}.ws",
                payload={
                    "channel": "run_state",
                    "event": "run_cancelled",
                    "runId": run_id,
                    "timestamp": now,
                    "payload": {"runId": run_id},
                },
            )
        else:
            await _mark_pending_stages_skipped(run_id=run_id)
            await _update_run_status(
                run_id=run_id,
                status="failed",
                failure_reason=captured_failure_reason,
                failure_stage=captured_failure_stage or None,
            )
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
                    },
                },
            )

    except Exception as exc:
        _active_processes.pop(run_id, None)
        await _update_run_status(
            run_id=run_id,
            status="failed",
            failure_reason=str(exc),
        )


async def cancel_run(*, session: AsyncSession, run_id: str) -> Run:
    run = await get_run(session=session, run_id=run_id)
    if run.status not in ("pending", "running"):
        raise ValueError(f"Run {run_id} is not cancellable in status {run.status}")

    proc = _active_processes.get(run_id)
    if proc is not None:
        with contextlib.suppress(ProcessLookupError):
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
        with contextlib.suppress(ProcessLookupError, OSError):
            proc.send_signal(_signal.SIGSTOP)

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

    child_payload = RunCreate(
        config_version_id=parent_run.config_version_id,
        parent_run_id=run_id,
    )
    return await create_run(session=session, project_id=project_id, payload=child_payload)
