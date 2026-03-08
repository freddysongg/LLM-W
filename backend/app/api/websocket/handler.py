from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import event_bus

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_CHANNELS = frozenset({"run_state", "metrics", "logs", "system"})


class _ConnectionState:
    def __init__(self, *, project_id: str, run_id: str | None) -> None:
        self.project_id = project_id
        self.run_id = run_id
        self.subscribed_channels: set[str] = set()

    def is_subscribed(self, channel: str) -> bool:
        return channel in self.subscribed_channels

    def subscribe(self, channels: list[str]) -> None:
        for ch in channels:
            if ch in _VALID_CHANNELS:
                self.subscribed_channels.add(ch)

    def unsubscribe(self, channels: list[str]) -> None:
        for ch in channels:
            self.subscribed_channels.discard(ch)


async def _send_json(websocket: WebSocket, message: dict[str, Any]) -> None:
    with contextlib.suppress(Exception):
        await websocket.send_text(json.dumps(message))


@router.websocket("/ws/{project_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    project_id: str,
    run_id: str | None = None,
) -> None:
    await websocket.accept()

    state = _ConnectionState(project_id=project_id, run_id=run_id)

    connected_at = datetime.now(UTC).isoformat()
    await _send_json(
        websocket,
        {
            "channel": "system",
            "event": "connected",
            "run_id": run_id,
            "timestamp": connected_at,
            "payload": {"project_id": project_id},
        },
    )

    async def _on_event(payload: dict[str, Any]) -> None:
        channel = payload.get("channel", "")
        if not state.is_subscribed(channel):
            return
        event_run_id = payload.get("run_id")
        if state.run_id is not None and event_run_id != state.run_id:
            return
        await _send_json(websocket, payload)

    event_type = f"project.{project_id}.ws"
    event_bus.subscribe(event_type=event_type, handler=_on_event)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await _send_json(
                    websocket,
                    {"channel": "system", "event": "error", "payload": {"message": "invalid JSON"}},
                )
                continue

            msg_type = message.get("type", "")
            msg_payload = message.get("payload", {})

            if msg_type == "subscribe":
                channels = msg_payload.get("channels", [])
                state.subscribe(channels)
                await _send_json(
                    websocket,
                    {
                        "channel": "system",
                        "event": "subscribed",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "payload": {"channels": list(state.subscribed_channels)},
                    },
                )

            elif msg_type == "unsubscribe":
                channels = msg_payload.get("channels", [])
                state.unsubscribe(channels)

            elif msg_type == "ping":
                await _send_json(
                    websocket,
                    {
                        "channel": "system",
                        "event": "pong",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "payload": {},
                    },
                )

    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(event_type=event_type, handler=_on_event)
