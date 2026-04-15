"""Integration tests for the accelerate-wrapped trainer.

Verifies the stdout JSON event contract is preserved across the refactor
and that the #53 callback stage-name collision is fixed.

These tests require the `training` optional extras (`torch`, `transformers`,
`accelerate`, `peft`, `trl`, `datasets`). The suite skips gracefully when any
of those are missing so the default backend venv stays green.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("accelerate")
pytest.importorskip("peft")
pytest.importorskip("trl")
pytest.importorskip("datasets")


TINY_MODEL_ID = "hf-internal-testing/tiny-random-GPT2"
TINY_TRAIN_ROWS = 16
TINY_MAX_SEQ_LENGTH = 32
TINY_EPOCHS = 1
TINY_BATCH_SIZE = 2
TINY_GRAD_ACCUM = 1


def _write_tiny_dataset(*, dataset_path: Path) -> None:
    rows = [{"prompt": f"hello {i}", "response": f"world {i}"} for i in range(TINY_TRAIN_ROWS)]
    with dataset_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _build_tiny_config(*, dataset_path: Path, project_dir: Path) -> dict[str, object]:
    return {
        "project": {"name": "trainer-accelerate-test"},
        "model": {
            "model_id": TINY_MODEL_ID,
            "torch_dtype": "float32",
            "trust_remote_code": False,
        },
        "dataset": {
            "source": "local_jsonl",
            "dataset_id": str(dataset_path),
            "train_split": "train",
            # Reuse the train split as eval so SFTTrainer invokes on_evaluate
            # mid-run, exercising WorkbenchCallback's callback_evaluation
            # stage emission and validating the #53 collision fix.
            "eval_split": "train",
            "input_field": "prompt",
            "target_field": "response",
            "max_samples": TINY_TRAIN_ROWS,
        },
        "preprocessing": {"max_seq_length": TINY_MAX_SEQ_LENGTH},
        "training": {
            "epochs": TINY_EPOCHS,
            "batch_size": TINY_BATCH_SIZE,
            "gradient_accumulation_steps": TINY_GRAD_ACCUM,
            "learning_rate": 5e-4,
            "weight_decay": 0.0,
            "max_grad_norm": 1.0,
            "seed": 7,
            "save_steps": 2,
            "logging_steps": 1,
            "eval_steps": 2,
        },
        "optimization": {
            "mixed_precision": "no",
            "scheduler": "linear",
            "gradient_checkpointing": False,
            "warmup_steps": 0,
            "warmup_ratio": 0.0,
        },
        "adapters": {"enabled": False},
        "quantization": {"enabled": False},
        "execution": {"device": "cpu", "environment": "local"},
    }


def _parse_stdout_events(stdout_text: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line in stdout_text.splitlines():
        stripped = line.strip()
        if not stripped or not stripped.startswith("{"):
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and "type" in event:
            events.append(event)
    return events


def _run_trainer_subprocess(
    *, run_id: str, config_path: Path, project_dir: Path
) -> subprocess.CompletedProcess[str]:
    backend_root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "TRANSFORMERS_VERBOSITY": "error"}
    return subprocess.run(
        [
            sys.executable,
            "-u",
            "-m",
            "app.services.trainer",
            "--run-id",
            run_id,
            "--config-path",
            str(config_path),
            "--project-dir",
            str(project_dir),
            "--heartbeat-interval",
            "60",
        ],
        cwd=str(backend_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


@pytest.fixture
def tiny_training_env(tmp_path: Path) -> tuple[str, Path, Path]:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    dataset_path = tmp_path / "tiny-dataset.jsonl"
    _write_tiny_dataset(dataset_path=dataset_path)
    config_dict = _build_tiny_config(dataset_path=dataset_path, project_dir=project_dir)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config_dict))
    run_id = "test-run-0001"
    return run_id, config_path, project_dir


def test_trainer_subprocess_preserves_stdout_contract(
    tiny_training_env: tuple[str, Path, Path],
) -> None:
    run_id, config_path, project_dir = tiny_training_env
    completed = _run_trainer_subprocess(
        run_id=run_id, config_path=config_path, project_dir=project_dir
    )
    assert completed.returncode == 0, (
        f"trainer exited non-zero: stderr=\n{completed.stderr}\nstdout=\n{completed.stdout}"
    )

    events = _parse_stdout_events(completed.stdout)
    assert events, "expected at least one JSON event on stdout"

    event_types = {event["type"] for event in events}
    for required in (
        "stage_enter",
        "stage_complete",
        "metric",
        "progress",
        "log",
        "complete",
    ):
        assert required in event_types, f"missing required event type '{required}' in {event_types}"

    complete_events = [event for event in events if event["type"] == "complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["status"] == "completed"


def test_trainer_subprocess_emits_expected_metric_fields(
    tiny_training_env: tuple[str, Path, Path],
) -> None:
    run_id, config_path, project_dir = tiny_training_env
    completed = _run_trainer_subprocess(
        run_id=run_id, config_path=config_path, project_dir=project_dir
    )
    assert completed.returncode == 0, completed.stderr

    events = _parse_stdout_events(completed.stdout)
    metric_events = [event for event in events if event["type"] == "metric"]
    assert metric_events, "expected at least one metric event"

    has_train_loss = any(
        "train_loss" in event.get("metrics", {})  # type: ignore[operator]
        for event in metric_events
    )
    assert has_train_loss, (
        "metric event must include renamed 'train_loss' key (not 'loss') — see b2fc54f"
    )

    tokens_per_second_values: list[float] = [
        float(event["metrics"]["tokens_per_second"])  # type: ignore[index]
        for event in metric_events
        if "tokens_per_second" in event.get("metrics", {})  # type: ignore[operator]
    ]
    assert tokens_per_second_values, (
        "expected at least one metric event with tokens_per_second — "
        "requires include_num_input_tokens_seen=True in SFTConfig"
    )
    assert any(value > 0 for value in tokens_per_second_values), (
        "expected a positive tokens_per_second after the first logging step"
    )

    # gpu_memory_used_mb relies on _sample_gpu_memory_mb() which returns None
    # on CPU-only hosts; only assert presence when an accelerator is available
    import torch  # noqa: PLC0415

    has_accelerator = torch.cuda.is_available() or torch.backends.mps.is_available()
    if has_accelerator:
        has_gpu_memory = any(
            "gpu_memory_used_mb" in event.get("metrics", {})  # type: ignore[operator]
            for event in metric_events
        )
        assert has_gpu_memory, "expected gpu_memory_used_mb on accelerator-equipped host"


def test_trainer_subprocess_writes_checkpoint_under_per_run_dir(
    tiny_training_env: tuple[str, Path, Path],
) -> None:
    run_id, config_path, project_dir = tiny_training_env
    completed = _run_trainer_subprocess(
        run_id=run_id, config_path=config_path, project_dir=project_dir
    )
    assert completed.returncode == 0, completed.stderr

    run_checkpoints_dir = project_dir / "runs" / run_id / "checkpoints"
    assert run_checkpoints_dir.exists(), (
        f"expected per-run checkpoints dir at {run_checkpoints_dir}"
    )

    events = _parse_stdout_events(completed.stdout)
    checkpoint_events = [event for event in events if event["type"] == "checkpoint"]
    assert checkpoint_events, "expected at least one checkpoint event"
    for event in checkpoint_events:
        path = str(event["path"])
        assert f"runs/{run_id}/checkpoints/" in path or (
            f"runs{os.sep}{run_id}{os.sep}checkpoints{os.sep}" in path
        )


def test_callback_evaluation_does_not_collide_with_reserved_stage_11(
    tiny_training_env: tuple[str, Path, Path],
) -> None:
    run_id, config_path, project_dir = tiny_training_env
    completed = _run_trainer_subprocess(
        run_id=run_id, config_path=config_path, project_dir=project_dir
    )
    assert completed.returncode == 0, completed.stderr

    events = _parse_stdout_events(completed.stdout)
    callback_stage_enters = [
        event
        for event in events
        if event["type"] == "stage_enter" and event.get("stage_name") == "callback_evaluation"
    ]
    reserved_stage_enters = [
        event
        for event in events
        if event["type"] == "stage_enter" and event.get("stage_name") == "evaluation"
    ]
    reserved_stage_completes = [
        event
        for event in events
        if event["type"] == "stage_complete" and event.get("stage_name") == "evaluation"
    ]
    assert callback_stage_enters, (
        "expected at least one 'callback_evaluation' stage_enter event — "
        "without eval_split wired the buggy version would pass this test vacuously"
    )
    assert len(reserved_stage_enters) == 1, (
        "expected exactly one reserved stage-11 'evaluation' enter event — "
        "callback must emit under a distinct stage name"
    )
    assert len(reserved_stage_completes) == 1
    assert "reserved no-op" in str(reserved_stage_completes[0].get("output_summary", ""))


def test_accelerator_announcement_log_emitted(
    tiny_training_env: tuple[str, Path, Path],
) -> None:
    run_id, config_path, project_dir = tiny_training_env
    completed = _run_trainer_subprocess(
        run_id=run_id, config_path=config_path, project_dir=project_dir
    )
    assert completed.returncode == 0, completed.stderr

    events = _parse_stdout_events(completed.stdout)
    log_events = [event for event in events if event["type"] == "log"]
    announced = any("Accelerator" in str(event.get("message", "")) for event in log_events)
    assert announced, "expected an environment_validation log message announcing the accelerator"
