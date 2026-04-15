from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.core.events import event_bus

_PROJECT_ID = "proj-ws"
_EVAL_RUN_ID = "er-ws-1"


class _RecordingHandler:
    def __init__(self) -> None:
        self.received: list[dict[str, Any]] = []

    async def __call__(self, payload: dict[str, Any]) -> None:
        self.received.append(payload)


@pytest.fixture
def recording_handler() -> _RecordingHandler:
    return _RecordingHandler()


async def test_case_completed_event_is_delivered_to_project_subscriber(
    recording_handler: _RecordingHandler,
) -> None:
    event_bus.subscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=recording_handler)
    try:
        envelope = {
            "channel": "eval",
            "event": "case_completed",
            "runId": _EVAL_RUN_ID,
            "timestamp": "2026-04-14T00:00:00+00:00",
            "payload": {
                "evalRunId": _EVAL_RUN_ID,
                "caseId": "case-1",
                "rubricVersionId": "rv-1",
                "evalCallId": "call-1",
                "verdict": "pass",
                "costUsd": 0.01,
                "latencyMs": 120,
            },
        }
        await event_bus.publish(event_type=f"project.{_PROJECT_ID}.ws", payload=envelope)
    finally:
        event_bus.unsubscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=recording_handler)

    assert len(recording_handler.received) == 1
    delivered = recording_handler.received[0]
    assert delivered["channel"] == "eval"
    assert delivered["event"] == "case_completed"
    assert delivered["payload"]["evalRunId"] == _EVAL_RUN_ID


async def test_eval_events_do_not_leak_across_projects(
    recording_handler: _RecordingHandler,
) -> None:
    event_bus.subscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=recording_handler)
    try:
        await event_bus.publish(
            event_type="project.other-project.ws",
            payload={
                "channel": "eval",
                "event": "case_completed",
                "runId": "er-other",
                "timestamp": "2026-04-14T00:00:00+00:00",
                "payload": {},
            },
        )
    finally:
        event_bus.unsubscribe(event_type=f"project.{_PROJECT_ID}.ws", handler=recording_handler)
    assert recording_handler.received == []


async def test_connection_manager_routes_eval_channel_to_subscribed_client() -> None:
    from app.api.websocket.stream import ConnectionManager

    manager = ConnectionManager()
    conn_id = 42
    conn = _register_connection(manager=manager, conn_id=conn_id)
    conn.subscribe(["eval"])

    payload = {
        "channel": "eval",
        "event": "run_completed",
        "runId": _EVAL_RUN_ID,
        "timestamp": "2026-04-14T00:00:00+00:00",
        "payload": {
            "evalRunId": _EVAL_RUN_ID,
            "status": "completed",
            "passRate": 1.0,
            "totalCostUsd": 0.05,
            "totals": {"cases": 1, "pass": 1, "fail": 0, "costUsdTotal": 0.05},
        },
    }
    await manager._route_event(conn_id=conn_id, payload=payload)

    enqueued = await asyncio.wait_for(conn.send_queue.get(), timeout=0.5)
    assert enqueued is not None
    assert enqueued["channel"] == "eval"
    assert enqueued["event"] == "run_completed"


async def test_connection_manager_drops_eval_event_when_channel_not_subscribed() -> None:
    from app.api.websocket.stream import ConnectionManager

    manager = ConnectionManager()
    conn_id = 99
    conn = _register_connection(manager=manager, conn_id=conn_id)
    conn.subscribe(["metrics"])

    payload = {
        "channel": "eval",
        "event": "cost_warning",
        "runId": _EVAL_RUN_ID,
        "timestamp": "2026-04-14T00:00:00+00:00",
        "payload": {"evalRunId": _EVAL_RUN_ID, "warningPct": 0.8},
    }
    await manager._route_event(conn_id=conn_id, payload=payload)

    assert conn.send_queue.empty()


def _register_connection(*, manager: Any, conn_id: int) -> Any:
    from app.api.websocket.stream import _ClientConnection

    conn = _ClientConnection(project_id=_PROJECT_ID, run_id=None)
    manager._connections[conn_id] = conn
    return conn
