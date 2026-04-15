from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.api.websocket.stream import connection_manager
from app.schemas.websocket import (
    WsPingFrame,
    WsSubscribeFrame,
    WsUnsubscribeFrame,
    ws_inbound_envelope_adapter,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_ERROR_INVALID_JSON = "INVALID_JSON"
_ERROR_INVALID_ENVELOPE = "INVALID_ENVELOPE"


async def _send_json(websocket: WebSocket, message: dict[str, Any]) -> None:
    with contextlib.suppress(Exception):
        await websocket.send_text(json.dumps(message))


def _error_frame(*, code: str, message: str) -> dict[str, Any]:
    return {
        "channel": "system",
        "event": "error",
        "type": "error",
        "run_id": None,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": {"code": code, "message": message},
    }


async def _dispatch_frame(*, websocket: WebSocket, frame: object) -> None:
    if isinstance(frame, WsSubscribeFrame):
        active_channels = connection_manager.handle_subscribe(
            websocket=websocket, channels=list(frame.payload.channels)
        )
        await _send_json(
            websocket,
            {
                "channel": "system",
                "event": "subscribed",
                "run_id": None,
                "timestamp": datetime.now(UTC).isoformat(),
                "payload": {"channels": list(active_channels)},
            },
        )
        return

    if isinstance(frame, WsUnsubscribeFrame):
        connection_manager.handle_unsubscribe(
            websocket=websocket, channels=list(frame.payload.channels)
        )
        return

    if isinstance(frame, WsPingFrame):
        await _send_json(
            websocket,
            {
                "channel": "system",
                "event": "pong",
                "run_id": None,
                "timestamp": datetime.now(UTC).isoformat(),
                "payload": {},
            },
        )
        return


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
                raw_message = json.loads(raw)
            except json.JSONDecodeError as exc:
                await _send_json(
                    websocket,
                    _error_frame(code=_ERROR_INVALID_JSON, message=str(exc)),
                )
                continue

            try:
                frame = ws_inbound_envelope_adapter.validate_python(raw_message)
            except ValidationError as exc:
                await _send_json(
                    websocket,
                    _error_frame(code=_ERROR_INVALID_ENVELOPE, message=exc.json()),
                )
                continue

            await _dispatch_frame(websocket=websocket, frame=frame)

    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(websocket=websocket)
