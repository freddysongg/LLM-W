from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("transformers")

from app.services import trainer  # noqa: E402


def test_final_eval_emits_stage_and_final_prefixed_metrics(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = MagicMock()
    fake.state.log_history = [{"loss": 0.5, "epoch": 1.0}]
    fake.state.global_step = 100
    fake.state.epoch = 1.0
    fake.evaluate.return_value = {"eval_loss": 0.42, "eval_runtime": 0.1}

    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_final_evaluation(hf_trainer=fake, has_eval_dataset=True)

    events = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    types_in_order = [e["type"] for e in events]
    assert types_in_order.index("stage_enter") < types_in_order.index("metric")
    assert types_in_order.index("metric") < types_in_order.index("stage_complete")

    enter = next(e for e in events if e["type"] == "stage_enter")
    assert enter["stage_name"] == "evaluation"
    assert enter["stage_order"] == 11

    metric_event = next(e for e in events if e["type"] == "metric")
    assert metric_event["metrics"]["final_eval_loss"] == 0.42

    complete = next(e for e in events if e["type"] == "stage_complete")
    assert "skipped" not in complete["output_summary"].lower()


def test_final_eval_marks_stage_skipped_when_no_eval_dataset(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = MagicMock()
    with patch.object(trainer, "_is_main_process", return_value=True):
        trainer._emit_final_evaluation(hf_trainer=fake, has_eval_dataset=False)

    events = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    complete = next(e for e in events if e["type"] == "stage_complete")
    assert "skipped" in complete["output_summary"].lower()
    fake.evaluate.assert_not_called()


def test_callback_evaluation_stage_name_still_used(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    heartbeat_state: dict[str, Any] = {
        "current_step": 0,
        "total_steps": 0,
        "stage": "training_progress",
        "metrics": {},
        "done": False,
    }
    callback = trainer.WorkbenchCallback(
        run_id="run-final-eval-test",
        project_dir=tmp_path,
        heartbeat_state=heartbeat_state,
    )
    fake_state = MagicMock()
    fake_state.global_step = 50
    fake_state.epoch = 0.5
    with patch.object(trainer, "_is_main_process", return_value=True):
        callback.on_evaluate(
            args=MagicMock(),
            state=fake_state,
            control=MagicMock(),
            metrics={"eval_loss": 0.7},
        )

    events = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    stage_names = {e.get("stage_name") for e in events if "stage_name" in e}
    assert trainer._CALLBACK_EVAL_STAGE_NAME in stage_names
    assert "evaluation" not in stage_names
