from __future__ import annotations

import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path

import psutil
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.run import Run

logger = logging.getLogger(__name__)

_TEMP_CHECKPOINT_PREFIX = ".tmp-checkpoint-"


def _is_pid_alive(pid: int) -> bool:
    return psutil.pid_exists(pid)


def _read_heartbeat(heartbeat_path: Path) -> dict[str, object] | None:
    if not heartbeat_path.exists():
        return None
    try:
        return json.loads(heartbeat_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _is_heartbeat_stale(heartbeat: dict[str, object]) -> bool:
    timestamp_raw = heartbeat.get("timestamp")
    if not isinstance(timestamp_raw, str):
        return True
    try:
        last_beat = datetime.fromisoformat(timestamp_raw)
        if last_beat.tzinfo is None:
            last_beat = last_beat.replace(tzinfo=UTC)
        elapsed = (datetime.now(UTC) - last_beat).total_seconds()
        return elapsed > settings.watchdog_stale_timeout_seconds
    except ValueError:
        return True


def _clean_temp_checkpoints(project_dir: Path) -> None:
    checkpoints_dir = project_dir / "checkpoints"
    if not checkpoints_dir.exists():
        return
    for entry in checkpoints_dir.iterdir():
        if entry.is_dir() and entry.name.startswith(_TEMP_CHECKPOINT_PREFIX):
            try:
                shutil.rmtree(entry)
                logger.info("cleaned temp checkpoint: %s", entry)
            except OSError:
                logger.warning("failed to clean temp checkpoint: %s", entry)


def _find_latest_valid_checkpoint(project_dir: Path) -> str | None:
    checkpoints_dir = project_dir / "checkpoints"
    if not checkpoints_dir.exists():
        return None
    valid = [
        e
        for e in checkpoints_dir.iterdir()
        if e.is_dir() and not e.name.startswith(_TEMP_CHECKPOINT_PREFIX)
        and e.name.startswith("checkpoint-")
    ]
    if not valid:
        return None
    valid.sort(key=lambda p: int(p.name.split("-")[-1]) if p.name.split("-")[-1].isdigit() else 0)
    return str(valid[-1])


async def _mark_run_failed(
    *,
    session: AsyncSession,
    run: Run,
    failure_reason: str,
    failure_stage: str | None,
    last_checkpoint_path: str | None,
) -> None:
    now = datetime.now(UTC).isoformat()
    run.status = "failed"
    run.failure_reason = failure_reason
    run.failure_stage = failure_stage
    run.completed_at = now
    run.updated_at = now
    if last_checkpoint_path is not None:
        run.last_checkpoint_path = last_checkpoint_path
    await session.commit()
    logger.info("marked run %s as failed: %s", run.id, failure_reason)


async def recover_stale_runs() -> None:
    """Called on app startup to recover runs that died while the app was down."""
    async with async_session_factory() as session:
        result = await session.execute(select(Run).where(Run.status == "running"))
        running_runs = list(result.scalars().all())

    for run in running_runs:
        async with async_session_factory() as session:
            refreshed = await session.get(Run, run.id)
            if refreshed is None:
                continue

            project_result = await session.execute(
                select(Run).where(Run.id == run.id)
            )
            target_run = project_result.scalar_one_or_none()
            if target_run is None:
                continue

            heartbeat: dict[str, object] | None = None
            if target_run.heartbeat_path:
                heartbeat = _read_heartbeat(Path(target_run.heartbeat_path))

            pid = target_run.pid
            pid_is_alive = pid is not None and _is_pid_alive(pid)

            if pid_is_alive and heartbeat is not None and not _is_heartbeat_stale(heartbeat):
                # Process is alive and healthy — reattach monitoring
                logger.info("run %s is alive (pid=%s), skipping recovery", target_run.id, pid)
                continue

            failure_stage: str | None = None
            if heartbeat is not None:
                stage_raw = heartbeat.get("stage")
                failure_stage = stage_raw if isinstance(stage_raw, str) else None

            project_dir = settings.projects_dir / (
                heartbeat.get("project_name") if heartbeat and "project_name" in heartbeat else ""
            )
            # Fallback: find project dir from run's heartbeat_path
            if target_run.heartbeat_path:
                project_dir = Path(target_run.heartbeat_path).parent

            last_checkpoint = _find_latest_valid_checkpoint(project_dir)
            _clean_temp_checkpoints(project_dir)

            await _mark_run_failed(
                session=session,
                run=target_run,
                failure_reason="Process terminated unexpectedly",
                failure_stage=failure_stage,
                last_checkpoint_path=last_checkpoint,
            )


async def check_run_health(*, run_id: str) -> bool:
    """Returns True if the run appears to be alive, False if it needs intervention."""
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None or run.status != "running":
            return False

        pid = run.pid
        if pid is None:
            return False

        if not _is_pid_alive(pid):
            return False

        if run.heartbeat_path:
            heartbeat = _read_heartbeat(Path(run.heartbeat_path))
            if heartbeat is None or _is_heartbeat_stale(heartbeat):
                return False

        return True
