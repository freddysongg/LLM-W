from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psutil
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.decision_log import DecisionLog
from app.models.run import Run

logger = logging.getLogger(__name__)

_IS_UNIX = sys.platform != "win32"
_IS_DARWIN = sys.platform == "darwin"

_TEMP_CHECKPOINT_PREFIX = ".tmp-checkpoint-"

_SIGNAL_NAMES: dict[int, str] = {
    1: "SIGHUP",
    2: "SIGINT",
    3: "SIGQUIT",
    4: "SIGILL",
    6: "SIGABRT",
    7: "SIGBUS",
    8: "SIGFPE",
    9: "SIGKILL",
    11: "SIGSEGV",
    13: "SIGPIPE",
    15: "SIGTERM",
}


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
        if e.is_dir()
        and not e.name.startswith(_TEMP_CHECKPOINT_PREFIX)
        and e.name.startswith("checkpoint-")
    ]
    if not valid:
        return None
    valid.sort(key=lambda p: int(p.name.split("-")[-1]) if p.name.split("-")[-1].isdigit() else 0)
    return str(valid[-1])


def _check_process_exit_unix(pid: int) -> str | None:
    """Try to determine how a process died via os.waitpid (Unix/macOS only)."""
    try:
        waited_pid, status = os.waitpid(pid, os.WNOHANG)
        if waited_pid == pid:
            if os.WIFSIGNALED(status):
                sig = os.WTERMSIG(status)
                name = _SIGNAL_NAMES.get(sig, f"signal {sig}")
                return f"killed by {name} ({sig})"
            if os.WIFEXITED(status):
                code = os.WEXITSTATUS(status)
                return f"exited with code {code}"
    except ChildProcessError:
        # Not a child of this process — cannot reap exit status
        pass
    except OSError:
        pass
    return None


def _check_process_exit_windows(pid: int) -> str | None:
    """Try to determine how a process exited using psutil (Windows only)."""
    try:
        exit_code = psutil.Process(pid).wait(timeout=0)
        return f"exited with code {exit_code}"
    except psutil.TimeoutExpired:
        # Process still alive — exit info not yet available
        pass
    except psutil.NoSuchProcess:
        # Process already gone from process table — exit status unavailable
        pass
    except psutil.AccessDenied:
        pass
    return None


def _check_process_exit_signal(pid: int) -> str | None:
    """Try to determine how a process died. Returns descriptive string or None."""
    if not _IS_UNIX:
        return _check_process_exit_windows(pid)
    return _check_process_exit_unix(pid)


def _check_macos_oom_kill(pid: int) -> bool:
    """Check if a process was OOM-killed on macOS by scanning the system log for jetsam events."""
    if not _IS_DARWIN:
        return False
    try:
        result = subprocess.run(
            [
                "log",
                "show",
                "--predicate",
                f'eventMessage CONTAINS[c] "jetsam" AND eventMessage CONTAINS[c] "{pid}"',
                "--last",
                "1h",
                "--style",
                "compact",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return str(pid) in result.stdout
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError):
        return False


def _build_failure_reason(heartbeat: dict[str, object] | None, pid: int | None) -> str:
    """Build a rich failure reason string from process exit info and last known heartbeat state."""
    parts: list[str] = ["Process terminated unexpectedly"]

    if pid is not None:
        exit_detail = _check_process_exit_signal(pid)
        if exit_detail:
            parts.append(exit_detail)
        elif _check_macos_oom_kill(pid):
            parts.append("OOM kill detected in system log")

    if heartbeat is not None:
        stage = heartbeat.get("stage")
        current_step = heartbeat.get("current_step")
        total_steps = heartbeat.get("total_steps")
        metrics = heartbeat.get("metrics")

        if isinstance(stage, str) and stage:
            parts.append(f"stage={stage}")

        if isinstance(current_step, int) and isinstance(total_steps, int) and total_steps > 0:
            parts.append(f"step={current_step}/{total_steps}")
        elif isinstance(current_step, int) and current_step > 0:
            parts.append(f"step={current_step}")

        if isinstance(metrics, dict) and metrics:
            metric_strs = [
                f"{k}={v:.4g}" for k, v in metrics.items() if isinstance(v, (int, float))
            ]
            if metric_strs:
                parts.append(f"last_metrics={{{', '.join(metric_strs)}}}")

    return "; ".join(parts)


def _resolve_project_dir(run: Run, heartbeat: dict[str, object] | None) -> Path:
    """Resolve the project directory from the run's heartbeat_path or heartbeat data."""
    if run.heartbeat_path:
        return Path(run.heartbeat_path).parent
    if heartbeat and isinstance(heartbeat.get("project_name"), str):
        return settings.projects_dir / str(heartbeat["project_name"])
    return settings.projects_dir


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

            project_result = await session.execute(select(Run).where(Run.id == run.id))
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

            project_dir = _resolve_project_dir(target_run, heartbeat)
            last_checkpoint = _find_latest_valid_checkpoint(project_dir)
            _clean_temp_checkpoints(project_dir)

            failure_reason = _build_failure_reason(heartbeat=heartbeat, pid=pid)

            await _mark_run_failed(
                session=session,
                run=target_run,
                failure_reason=failure_reason,
                failure_stage=failure_stage,
                last_checkpoint_path=last_checkpoint,
            )

            decision = DecisionLog(
                id=str(uuid.uuid4()),
                project_id=target_run.project_id,
                action_type="run_cancelled",
                actor="system",
                target_type="run",
                target_id=target_run.id,
                notes=f"watchdog recovery: {failure_reason}",
                created_at=datetime.now(UTC).isoformat(),
            )
            session.add(decision)
            await session.commit()


async def check_run_health(*, run_id: str) -> bool:
    """Returns True if the run appears alive, False after marking it failed with diagnostics."""
    async with async_session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None or run.status != "running":
            return False

        pid = run.pid
        if pid is None:
            await _mark_run_failed(
                session=session,
                run=run,
                failure_reason=_build_failure_reason(heartbeat=None, pid=None),
                failure_stage=None,
                last_checkpoint_path=None,
            )
            return False

        heartbeat: dict[str, object] | None = None
        if run.heartbeat_path:
            heartbeat = _read_heartbeat(Path(run.heartbeat_path))

        if not _is_pid_alive(pid):
            failure_stage: str | None = None
            if heartbeat is not None:
                stage_raw = heartbeat.get("stage")
                failure_stage = stage_raw if isinstance(stage_raw, str) else None
            project_dir = _resolve_project_dir(run, heartbeat)
            last_checkpoint = _find_latest_valid_checkpoint(project_dir)
            _clean_temp_checkpoints(project_dir)
            await _mark_run_failed(
                session=session,
                run=run,
                failure_reason=_build_failure_reason(heartbeat=heartbeat, pid=pid),
                failure_stage=failure_stage,
                last_checkpoint_path=last_checkpoint,
            )
            return False

        if heartbeat is None or _is_heartbeat_stale(heartbeat):
            stale_stage: str | None = None
            if heartbeat is not None:
                stage_raw = heartbeat.get("stage")
                stale_stage = stage_raw if isinstance(stage_raw, str) else None
            project_dir = _resolve_project_dir(run, heartbeat)
            last_checkpoint = _find_latest_valid_checkpoint(project_dir)
            _clean_temp_checkpoints(project_dir)
            await _mark_run_failed(
                session=session,
                run=run,
                failure_reason=_build_failure_reason(heartbeat=heartbeat, pid=pid),
                failure_stage=stale_stage,
                last_checkpoint_path=last_checkpoint,
            )
            return False

        return True
