"""Unit tests for rank-aware observability and atomic checkpointing.

Covers the behaviour required by issues #32 and #33 without launching a real
distributed run: `_is_main_process()` consults env vars before the
accelerator singleton is built, every `WorkbenchCallback` method is silent on
non-zero ranks, and `on_save` stamps a COMPLETE marker only after the
cross-rank barrier so resume never loads a half-written checkpoint.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("transformers")

from app.services import trainer  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_accelerator_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(trainer, "_ACCELERATOR", None)
    monkeypatch.delenv("RANK", raising=False)
    monkeypatch.delenv("LOCAL_RANK", raising=False)


def test_is_main_process_returns_true_when_no_accelerator_and_no_rank_env() -> None:
    assert trainer._is_main_process() is True


def test_is_main_process_returns_false_when_rank_env_is_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RANK", "1")
    assert trainer._is_main_process() is False


def test_is_main_process_returns_true_when_rank_env_is_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RANK", "0")
    assert trainer._is_main_process() is True


def test_is_main_process_defers_to_local_rank_when_only_local_rank_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCAL_RANK", "2")
    assert trainer._is_main_process() is False


def test_is_main_process_prefers_accelerator_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_accelerator = MagicMock()
    fake_accelerator.is_main_process = False
    monkeypatch.setattr(trainer, "_ACCELERATOR", fake_accelerator)
    monkeypatch.setenv("RANK", "0")
    assert trainer._is_main_process() is False


def test_emit_is_silent_on_non_main_rank(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("RANK", "1")
    trainer._emit({"type": "metric", "step": 1, "epoch": 0.0, "metrics": {}})
    captured = capsys.readouterr()
    assert captured.out == ""


def test_emit_writes_json_on_main_rank(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    trainer._emit({"type": "log", "severity": "info", "message": "hi", "stage": "x"})
    captured = capsys.readouterr()
    decoded = json.loads(captured.out.strip())
    assert decoded["type"] == "log"
    assert decoded["message"] == "hi"


def test_heartbeat_thread_skips_write_on_non_main_rank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RANK", "1")
    heartbeat_path = tmp_path / ".heartbeat"
    state: dict[str, Any] = {
        "current_step": 5,
        "total_steps": 10,
        "stage": "training_progress",
        "metrics": {"train_loss": 0.5},
        "done": False,
    }
    thread = trainer._start_heartbeat_thread(
        heartbeat_path=heartbeat_path,
        run_id="run-xyz",
        interval_seconds=0,
        state=state,
    )
    try:
        for _ in range(200):
            if heartbeat_path.exists():
                break
    finally:
        state["done"] = True
        thread.join(timeout=2.0)
    assert not heartbeat_path.exists()


def test_heartbeat_thread_writes_when_main_rank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    heartbeat_path = tmp_path / ".heartbeat"
    state: dict[str, Any] = {
        "current_step": 7,
        "total_steps": 10,
        "stage": "training_progress",
        "metrics": {},
        "done": False,
    }
    thread = trainer._start_heartbeat_thread(
        heartbeat_path=heartbeat_path,
        run_id="run-xyz",
        interval_seconds=0,
        state=state,
    )
    try:
        for _ in range(1000):
            if heartbeat_path.exists():
                break
    finally:
        state["done"] = True
        thread.join(timeout=2.0)
    assert heartbeat_path.exists()
    payload = json.loads(heartbeat_path.read_text())
    assert payload["run_id"] == "run-xyz"
    assert payload["current_step"] == 7


class _StubState:
    def __init__(self, *, global_step: int, max_steps: int, epoch: float) -> None:
        self.global_step = global_step
        self.max_steps = max_steps
        self.epoch = epoch


def _build_callback(tmp_path: Path) -> tuple[trainer.WorkbenchCallback, dict[str, Any]]:
    heartbeat_state: dict[str, Any] = {
        "current_step": 0,
        "total_steps": 0,
        "stage": "training_progress",
        "metrics": {},
        "done": False,
    }
    callback = trainer.WorkbenchCallback(
        run_id="run-xyz",
        project_dir=tmp_path,
        heartbeat_state=heartbeat_state,
    )
    return callback, heartbeat_state


def test_workbench_callback_methods_emit_nothing_on_non_main_rank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("RANK", "1")
    callback, heartbeat_state = _build_callback(tmp_path)
    state = _StubState(global_step=3, max_steps=10, epoch=0.3)

    callback.on_train_begin(args=None, state=state, control=None)
    callback.on_step_end(args=None, state=state, control=None)
    callback.on_log(args=None, state=state, control=None, logs={"loss": 0.2})
    callback.on_evaluate(args=None, state=state, control=None, metrics={"eval_loss": 0.3})
    callback.on_train_end(args=None, state=state, control=None)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert heartbeat_state["current_step"] == 0
    assert heartbeat_state["total_steps"] == 0


def test_workbench_callback_emits_when_main_rank(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    callback, _ = _build_callback(tmp_path)
    state = _StubState(global_step=3, max_steps=10, epoch=0.3)
    callback.on_step_end(args=None, state=state, control=None)
    captured = capsys.readouterr()
    events = [json.loads(line) for line in captured.out.strip().splitlines() if line.strip()]
    assert any(event["type"] == "progress" and event["current_step"] == 3 for event in events)


def test_on_save_writes_complete_marker_and_emits_checkpoint_on_main_rank(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_id = "run-xyz"
    step = 4
    checkpoint_dir = (
        trainer._run_checkpoints_dir(project_dir=tmp_path, run_id=run_id) / f"checkpoint-{step}"
    )
    checkpoint_dir.mkdir(parents=True)
    (checkpoint_dir / "model.safetensors").write_bytes(b"stub")

    callback = trainer.WorkbenchCallback(
        run_id=run_id,
        project_dir=tmp_path,
        heartbeat_state={
            "current_step": 0,
            "total_steps": 0,
            "stage": "training_progress",
            "metrics": {},
            "done": False,
        },
    )
    state = _StubState(global_step=step, max_steps=10, epoch=0.4)
    callback.on_save(args=None, state=state, control=None)

    assert (checkpoint_dir / trainer._CHECKPOINT_COMPLETE_MARKER).is_file()
    assert trainer._is_checkpoint_complete(checkpoint_dir)

    captured = capsys.readouterr()
    events = [json.loads(line) for line in captured.out.strip().splitlines() if line.strip()]
    checkpoint_events = [event for event in events if event["type"] == "checkpoint"]
    assert len(checkpoint_events) == 1
    assert checkpoint_events[0]["step"] == step
    assert checkpoint_events[0]["path"] == str(checkpoint_dir)


def test_on_save_barrier_is_called_before_rank_zero_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    call_order: list[str] = []

    fake_accelerator = MagicMock()
    fake_accelerator.is_main_process = True

    def _fake_wait() -> None:
        call_order.append("wait_for_everyone")

    fake_accelerator.wait_for_everyone.side_effect = _fake_wait
    monkeypatch.setattr(trainer, "_ACCELERATOR", fake_accelerator)

    original_marker = trainer._write_checkpoint_complete_marker

    def _tracing_marker(*, checkpoint_dir: Path, step: int) -> None:
        call_order.append("write_marker")
        original_marker(checkpoint_dir=checkpoint_dir, step=step)

    monkeypatch.setattr(trainer, "_write_checkpoint_complete_marker", _tracing_marker)

    run_id = "run-xyz"
    step = 8
    checkpoint_dir = (
        trainer._run_checkpoints_dir(project_dir=tmp_path, run_id=run_id) / f"checkpoint-{step}"
    )
    checkpoint_dir.mkdir(parents=True)

    callback = trainer.WorkbenchCallback(
        run_id=run_id,
        project_dir=tmp_path,
        heartbeat_state={
            "current_step": 0,
            "total_steps": 0,
            "stage": "training_progress",
            "metrics": {},
            "done": False,
        },
    )
    state = _StubState(global_step=step, max_steps=10, epoch=0.8)

    # Silence stdout while exercising the barrier order
    sys.stdout = io.StringIO()
    try:
        callback.on_save(args=None, state=state, control=None)
    finally:
        sys.stdout = sys.__stdout__

    assert call_order == ["wait_for_everyone", "write_marker"]


def test_on_save_on_non_main_rank_skips_marker_and_emits_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_accelerator = MagicMock()
    fake_accelerator.is_main_process = False
    monkeypatch.setattr(trainer, "_ACCELERATOR", fake_accelerator)

    run_id = "run-xyz"
    step = 2
    checkpoint_dir = (
        trainer._run_checkpoints_dir(project_dir=tmp_path, run_id=run_id) / f"checkpoint-{step}"
    )
    checkpoint_dir.mkdir(parents=True)

    callback = trainer.WorkbenchCallback(
        run_id=run_id,
        project_dir=tmp_path,
        heartbeat_state={
            "current_step": 0,
            "total_steps": 0,
            "stage": "training_progress",
            "metrics": {},
            "done": False,
        },
    )
    state = _StubState(global_step=step, max_steps=10, epoch=0.2)
    callback.on_save(args=None, state=state, control=None)

    fake_accelerator.wait_for_everyone.assert_called_once()
    assert not (checkpoint_dir / trainer._CHECKPOINT_COMPLETE_MARKER).exists()
    captured = capsys.readouterr()
    assert captured.out == ""


def test_write_checkpoint_complete_marker_is_atomic(tmp_path: Path) -> None:
    checkpoint_dir = tmp_path / "checkpoint-9"
    checkpoint_dir.mkdir()
    trainer._write_checkpoint_complete_marker(checkpoint_dir=checkpoint_dir, step=9)
    marker = checkpoint_dir / trainer._CHECKPOINT_COMPLETE_MARKER
    assert marker.is_file()
    payload = json.loads(marker.read_text())
    assert payload["step"] == 9
    assert "completed_at" in payload
    # The `.COMPLETE.tmp` staging file must not leak after rename
    leftover = list(checkpoint_dir.glob(".*.tmp"))
    assert leftover == []


def test_is_checkpoint_complete_detects_missing_marker(tmp_path: Path) -> None:
    partial = tmp_path / "checkpoint-3"
    partial.mkdir()
    (partial / "model.safetensors").write_bytes(b"x")
    assert trainer._is_checkpoint_complete(partial) is False

    trainer._write_checkpoint_complete_marker(checkpoint_dir=partial, step=3)
    assert trainer._is_checkpoint_complete(partial) is True


def test_stdout_event_contract_unchanged_after_rank_gating(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    callback, _ = _build_callback(tmp_path)
    state = _StubState(global_step=1, max_steps=4, epoch=0.25)
    callback.on_train_begin(args=None, state=state, control=None)
    callback.on_step_end(args=None, state=state, control=None)
    callback.on_log(args=None, state=state, control=None, logs={"loss": 1.23})
    callback.on_evaluate(args=None, state=state, control=None, metrics={"eval_loss": 0.5})

    captured = capsys.readouterr()
    events = [json.loads(line) for line in captured.out.strip().splitlines() if line.strip()]
    event_types = {event["type"] for event in events}
    assert "progress" in event_types
    assert "metric" in event_types
    assert "stage_enter" in event_types
    assert "stage_complete" in event_types

    for event in events:
        if event["type"] == "progress":
            assert {"current_step", "total_steps", "progress_pct", "epoch"} <= event.keys()
        if event["type"] == "metric":
            assert {"step", "epoch", "metrics"} <= event.keys()
