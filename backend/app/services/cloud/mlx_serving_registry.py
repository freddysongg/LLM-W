"""In-memory registry of active MLX serving adapters keyed by project id.

Owns the `dict[ProjectId, MLXServingAdapter]` state map referenced in the
design doc plus the lifecycle calls the HTTP route layer delegates to.
The registry is also responsible for cross-project capacity enforcement:
v1 caps the workbench at one active serve at a time to prevent unified
memory from being pinned by a stale supervisor.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.schemas.mlx_serving import ServingStatus

if TYPE_CHECKING:
    # Avoid eager import: keep `mlx_lm` cost out of base/local installs.
    from app.services.cloud.mlx_serving import MLXServingAdapter

logger = logging.getLogger(__name__)

_MAX_CONCURRENT_SERVES: int = 1


class ServingCapacityExceededError(Exception):
    """Raised when the workbench-wide serving cap would be exceeded."""

    def __init__(self, *, active_project_id: str) -> None:
        super().__init__(
            "Workbench is already serving a model "
            f"(project {active_project_id}). Stop it before starting another."
        )
        self.active_project_id = active_project_id


class ServingNotRunningError(Exception):
    """Raised when stop is requested for a project that has no active adapter."""

    def __init__(self, project_id: str) -> None:
        super().__init__(f"No active serving adapter for project {project_id}.")
        self.project_id = project_id


@dataclass
class _ActiveServe:
    adapter: MLXServingAdapter
    project_id: str
    model_id: str
    adapter_path: str | None
    started_at: str
    last_error: str | None = None
    event_drain_task: asyncio.Task[None] | None = field(default=None)


_active: dict[str, _ActiveServe] = {}
_lock: asyncio.Lock = asyncio.Lock()


def get_status(*, project_id: str) -> ServingStatus:
    entry = _active.get(project_id)
    if entry is None:
        return ServingStatus(
            project_id=project_id,
            state="stopped",
        )
    adapter = entry.adapter
    return ServingStatus(
        project_id=project_id,
        state="running",
        base_url=_safe_base_url(adapter=adapter),
        model_id=entry.model_id,
        adapter_path=entry.adapter_path,
        pid=adapter.pid,
        started_at=entry.started_at,
        last_error=entry.last_error,
    )


async def start_serving(
    *,
    project_id: str,
    serving_model_id: str,
    adapter_path: Path | None,
    trust_remote_code: bool,
) -> ServingStatus:
    """Start (or restart) MLX serving for a project.

    If the workbench already has a serve running for a different project the
    request is rejected with `ServingCapacityExceededError`. If the same
    project already has a serve running, the old supervisor is stopped first
    so the request behaves as a restart.
    """
    from app.services.cloud.mlx_serving import (
        MLXServingAdapter,
        MLXServingConfig,
    )

    async with _lock:
        existing = _active.get(project_id)
        if existing is None and len(_active) >= _MAX_CONCURRENT_SERVES:
            other_project = next(iter(_active))
            raise ServingCapacityExceededError(active_project_id=other_project)
        if existing is not None:
            await _stop_locked(project_id=project_id)

        config = MLXServingConfig(
            project_id=project_id,
            serving_model_id=serving_model_id,
            adapter_path=adapter_path,
            trust_remote_code=trust_remote_code,
        )
        adapter = MLXServingAdapter(config=config)
        await adapter.start()

        started_at = datetime.now(UTC).isoformat()
        entry = _ActiveServe(
            adapter=adapter,
            project_id=project_id,
            model_id=serving_model_id,
            adapter_path=str(adapter_path) if adapter_path is not None else None,
            started_at=started_at,
        )
        entry.event_drain_task = asyncio.create_task(
            _drain_events(project_id=project_id, adapter=adapter),
            name=f"mlx-serving-drain-{project_id}",
        )
        _active[project_id] = entry

    return get_status(project_id=project_id)


async def stop_serving(*, project_id: str) -> None:
    async with _lock:
        if project_id not in _active:
            raise ServingNotRunningError(project_id)
        await _stop_locked(project_id=project_id)


async def shutdown_all() -> None:
    """Stop every active serve. Invoked from app lifespan teardown / tests."""
    async with _lock:
        project_ids = list(_active.keys())
        for project_id in project_ids:
            try:
                await _stop_locked(project_id=project_id)
            except Exception:
                logger.warning(
                    "Failed to stop serving adapter for project %s during shutdown",
                    project_id,
                    exc_info=True,
                )


async def _stop_locked(*, project_id: str) -> None:
    entry = _active.pop(project_id, None)
    if entry is None:
        return
    try:
        await entry.adapter.cancel()
    finally:
        if entry.event_drain_task is not None and not entry.event_drain_task.done():
            entry.event_drain_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await entry.event_drain_task


async def _drain_events(*, project_id: str, adapter: MLXServingAdapter) -> None:
    """Consume adapter events so the queue does not back up indefinitely.

    Serving has no per-step training events, just a small fixed set
    (`serving_ready`, `log`, `serving_stopped`). The drain task surfaces
    nothing externally yet — a future WS bridge can subscribe here.
    """
    while True:
        try:
            event = await adapter.read_event()
        except asyncio.CancelledError:
            return
        if event is None:
            return
        event_type = event.get("type")
        if event_type == "log":
            logger.debug("[mlx-serving %s] %s", project_id, event.get("message"))


def _safe_base_url(*, adapter: MLXServingAdapter) -> str | None:
    try:
        return adapter.base_url
    except RuntimeError:
        return None
