from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import psutil
from fastapi import WebSocket

from app.core.events import event_bus

logger = logging.getLogger(__name__)

_VALID_CHANNELS = frozenset({"run_state", "metrics", "logs", "system"})
_QUEUE_MAX_SIZE = 256
_RESOURCE_POLL_INTERVAL = 5.0

EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


def _make_send_queue() -> asyncio.Queue[dict[str, Any] | None]:
    return asyncio.Queue(maxsize=_QUEUE_MAX_SIZE)


@dataclass
class _ClientConnection:
    project_id: str
    run_id: str | None
    subscribed_channels: set[str] = field(default_factory=set)
    send_queue: asyncio.Queue[dict[str, Any] | None] = field(default_factory=_make_send_queue)

    def is_subscribed(self, channel: str) -> bool:
        return channel in self.subscribed_channels

    def subscribe(self, channels: list[str]) -> None:
        for ch in channels:
            if ch in _VALID_CHANNELS:
                self.subscribed_channels.add(ch)

    def unsubscribe(self, channels: list[str]) -> None:
        for ch in channels:
            self.subscribed_channels.discard(ch)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, _ClientConnection] = {}
        self._websockets: dict[int, WebSocket] = {}
        self._sender_tasks: dict[int, asyncio.Task[None]] = {}
        self._event_handlers: dict[int, EventHandler] = {}
        self._resource_poller: asyncio.Task[None] | None = None

    async def connect(
        self,
        *,
        websocket: WebSocket,
        project_id: str,
        run_id: str | None,
        initial_channels: list[str],
    ) -> None:
        conn_id = id(websocket)
        conn = _ClientConnection(project_id=project_id, run_id=run_id)
        conn.subscribe(initial_channels)

        self._connections[conn_id] = conn
        self._websockets[conn_id] = websocket

        sender = asyncio.create_task(self._drain_queue(conn_id=conn_id))
        self._sender_tasks[conn_id] = sender

        async def _on_event(payload: dict[str, Any]) -> None:
            await self._route_event(conn_id=conn_id, payload=payload)

        self._event_handlers[conn_id] = _on_event
        event_bus.subscribe(
            event_type=f"project.{project_id}.ws",
            handler=_on_event,
        )

    async def disconnect(self, *, websocket: WebSocket) -> None:
        conn_id = id(websocket)
        conn = self._connections.pop(conn_id, None)
        self._websockets.pop(conn_id, None)

        if conn is None:
            return

        handler = self._event_handlers.pop(conn_id, None)
        if handler is not None:
            event_bus.unsubscribe(
                event_type=f"project.{conn.project_id}.ws",
                handler=handler,
            )

        with contextlib.suppress(asyncio.QueueFull):
            conn.send_queue.put_nowait(None)

        sender = self._sender_tasks.pop(conn_id, None)
        if sender is not None:
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sender

    def handle_subscribe(self, *, websocket: WebSocket, channels: list[str]) -> set[str]:
        conn = self._connections.get(id(websocket))
        if conn is None:
            return set()
        conn.subscribe(channels)
        return conn.subscribed_channels

    def handle_unsubscribe(self, *, websocket: WebSocket, channels: list[str]) -> None:
        conn = self._connections.get(id(websocket))
        if conn is None:
            return
        conn.unsubscribe(channels)

    async def _route_event(self, *, conn_id: int, payload: dict[str, Any]) -> None:
        conn = self._connections.get(conn_id)
        if conn is None:
            return

        channel = payload.get("channel", "")
        if not conn.is_subscribed(channel):
            return

        event_run_id = payload.get("runId")
        if conn.run_id is not None and event_run_id != conn.run_id:
            return

        try:
            conn.send_queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning(
                "send queue full for connection %d, dropping event channel=%s",
                conn_id,
                channel,
            )

    async def _drain_queue(self, *, conn_id: int) -> None:
        conn = self._connections.get(conn_id)
        websocket = self._websockets.get(conn_id)
        if conn is None or websocket is None:
            return

        while True:
            message = await conn.send_queue.get()
            if message is None:
                break
            with contextlib.suppress(Exception):
                await websocket.send_text(json.dumps(message))

    async def start_resource_poller(self) -> None:
        if self._resource_poller is not None:
            return
        self._resource_poller = asyncio.create_task(self._poll_resources())

    async def stop_resource_poller(self) -> None:
        if self._resource_poller is None:
            return
        self._resource_poller.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._resource_poller
        self._resource_poller = None

    async def _poll_resources(self) -> None:
        while True:
            await asyncio.sleep(_RESOURCE_POLL_INTERVAL)
            try:
                raw = _collect_system_resources()
                resource_payload = {
                    "gpuMemoryUsedMb": raw["gpu_memory_used_mb"],
                    "gpuUtilizationPct": raw["gpu_utilization_pct"],
                    "cpuPct": raw["cpu_pct"],
                    "ramUsedMb": raw["ram_used_mb"],
                }
            except Exception:
                logger.exception("failed to collect system resources")
                continue

            project_ids = {conn.project_id for conn in self._connections.values()}
            for project_id in project_ids:
                await event_bus.publish(
                    event_type=f"project.{project_id}.ws",
                    payload={
                        "channel": "system",
                        "event": "resource_update",
                        "runId": None,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "payload": resource_payload,
                    },
                )


def _collect_system_resources() -> dict[str, float]:
    cpu_pct = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()
    ram_used_mb = ram.used / (1024 * 1024)

    gpu_memory_used_mb = 0.0
    gpu_utilization_pct = 0.0

    try:
        import torch  # noqa: PLC0415

        if torch.cuda.is_available():
            gpu_memory_used_mb = torch.cuda.memory_allocated() / (1024 * 1024)
            # utilization not reliably available without pynvml
        elif torch.backends.mps.is_available():
            gpu_memory_used_mb = torch.mps.current_allocated_memory() / (1024 * 1024)
    except Exception:
        pass

    return {
        "gpu_memory_used_mb": gpu_memory_used_mb,
        "gpu_utilization_pct": gpu_utilization_pct,
        "cpu_pct": cpu_pct,
        "ram_used_mb": ram_used_mb,
    }


connection_manager = ConnectionManager()
