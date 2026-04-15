from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.api.websocket import handler as ws_handler
from app.api.websocket.stream import ConnectionManager, _ClientConnection
from app.schemas.websocket import (
    WsPingFrame,
    WsSubscribeFrame,
    WsUnsubscribeFrame,
    ws_inbound_envelope_adapter,
)

_PROJECT_ID = "proj-ws-validation"


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_text(self, payload: str) -> None:
        self.sent.append(json.loads(payload))


def _install_connection(
    *, manager: ConnectionManager, fake_ws: _FakeWebSocket
) -> _ClientConnection:
    conn = _ClientConnection(project_id=_PROJECT_ID, run_id=None)
    manager._connections[id(fake_ws)] = conn
    manager._websockets[id(fake_ws)] = fake_ws  # type: ignore[assignment]
    return conn


def test_valid_subscribe_frame_parses_into_discriminated_model() -> None:
    frame = ws_inbound_envelope_adapter.validate_python(
        {"type": "subscribe", "payload": {"channels": ["metrics", "logs"]}}
    )
    assert isinstance(frame, WsSubscribeFrame)
    assert frame.payload.channels == ["metrics", "logs"]


def test_valid_unsubscribe_frame_parses_into_discriminated_model() -> None:
    frame = ws_inbound_envelope_adapter.validate_python(
        {"type": "unsubscribe", "payload": {"channels": ["eval"]}}
    )
    assert isinstance(frame, WsUnsubscribeFrame)
    assert frame.payload.channels == ["eval"]


def test_valid_ping_frame_parses_into_discriminated_model() -> None:
    frame = ws_inbound_envelope_adapter.validate_python({"type": "ping"})
    assert isinstance(frame, WsPingFrame)


def test_missing_type_field_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        ws_inbound_envelope_adapter.validate_python({"payload": {"channels": ["metrics"]}})


def test_unknown_type_value_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        ws_inbound_envelope_adapter.validate_python(
            {"type": "bogus", "payload": {"channels": ["metrics"]}}
        )


def test_invalid_channel_value_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        ws_inbound_envelope_adapter.validate_python(
            {"type": "subscribe", "payload": {"channels": ["not-a-real-channel"]}}
        )


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        ws_inbound_envelope_adapter.validate_python(
            {
                "type": "subscribe",
                "payload": {"channels": ["metrics"]},
                "stray": "nope",
            }
        )


async def test_dispatch_subscribe_frame_activates_channels(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = ConnectionManager()
    monkeypatch.setattr(ws_handler, "connection_manager", manager)
    fake_ws = _FakeWebSocket()
    conn = _install_connection(manager=manager, fake_ws=fake_ws)

    frame = ws_inbound_envelope_adapter.validate_python(
        {"type": "subscribe", "payload": {"channels": ["metrics", "logs"]}}
    )
    await ws_handler._dispatch_frame(websocket=fake_ws, frame=frame)  # type: ignore[arg-type]

    assert conn.subscribed_channels == {"metrics", "logs"}
    assert len(fake_ws.sent) == 1
    ack = fake_ws.sent[0]
    assert ack["event"] == "subscribed"
    assert set(ack["payload"]["channels"]) == {"metrics", "logs"}


async def test_dispatch_unsubscribe_frame_removes_channels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ConnectionManager()
    monkeypatch.setattr(ws_handler, "connection_manager", manager)
    fake_ws = _FakeWebSocket()
    conn = _install_connection(manager=manager, fake_ws=fake_ws)
    conn.subscribe(["metrics", "logs"])

    frame = ws_inbound_envelope_adapter.validate_python(
        {"type": "unsubscribe", "payload": {"channels": ["logs"]}}
    )
    await ws_handler._dispatch_frame(websocket=fake_ws, frame=frame)  # type: ignore[arg-type]

    assert conn.subscribed_channels == {"metrics"}


async def test_dispatch_ping_frame_sends_pong(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = ConnectionManager()
    monkeypatch.setattr(ws_handler, "connection_manager", manager)
    fake_ws = _FakeWebSocket()
    _install_connection(manager=manager, fake_ws=fake_ws)

    frame = ws_inbound_envelope_adapter.validate_python({"type": "ping"})
    await ws_handler._dispatch_frame(websocket=fake_ws, frame=frame)  # type: ignore[arg-type]

    assert len(fake_ws.sent) == 1
    assert fake_ws.sent[0]["event"] == "pong"


def test_error_frame_helper_uses_invalid_envelope_code() -> None:
    envelope = ws_handler._error_frame(code=ws_handler._ERROR_INVALID_ENVELOPE, message="bad shape")
    assert envelope["type"] == "error"
    assert envelope["event"] == "error"
    assert envelope["channel"] == "system"
    assert envelope["payload"]["code"] == "INVALID_ENVELOPE"
    assert envelope["payload"]["message"] == "bad shape"


def test_error_frame_helper_uses_invalid_json_code() -> None:
    envelope = ws_handler._error_frame(
        code=ws_handler._ERROR_INVALID_JSON, message="Expecting value"
    )
    assert envelope["payload"]["code"] == "INVALID_JSON"
