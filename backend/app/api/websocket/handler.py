from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.websocket.stream import connection_manager

logger = logging.getLogger(__name__)

router = APIRouter()


async def _send_json(websocket: WebSocket, message: dict[str, Any]) -> None:
    with contextlib.suppress(Exception):
        await websocket.send_text(json.dumps(message))


@router.websocket("/ws/{project_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    project_id: str,
    run_id: str | None = None,
    channels: str | None = None,
) -> None:
    await websocket.accept()

    initial_channels = [ch.strip() for ch in channels.split(",") if ch.strip()] if channels else []

    await connection_manager.connect(
        websocket=websocket,
        project_id=project_id,
        run_id=run_id,
        initial_channels=initial_channels,
    )

    await _send_json(
        websocket,
        {
            "channel": "system",
            "event": "connected",
            "run_id": run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": {"project_id": project_id},
        },
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await _send_json(
                    websocket,
                    {
                        "channel": "system",
                        "event": "error",
                        "payload": {"message": "invalid JSON"},
                    },
                )
                continue

            msg_type = message.get("type", "")
            msg_payload = message.get("payload", {})

            if msg_type == "subscribe":
                channel_list = msg_payload.get("channels", [])
                active_channels = connection_manager.handle_subscribe(
                    websocket=websocket, channels=channel_list
                )
                await _send_json(
                    websocket,
                    {
                        "channel": "system",
                        "event": "subscribed",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "payload": {"channels": list(active_channels)},
                    },
                )

            elif msg_type == "unsubscribe":
                channel_list = msg_payload.get("channels", [])
                connection_manager.handle_unsubscribe(websocket=websocket, channels=channel_list)

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
        await connection_manager.disconnect(websocket=websocket)
