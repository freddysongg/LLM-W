from __future__ import annotations

from pathlib import Path

from app.services.cloud.modal_adapter import (
    ModalAdapterConfig,
    ModalTrainingAdapter,
    translate_workspace_path,
)


def _make_adapter(*, project_dir: Path) -> ModalTrainingAdapter:
    config = ModalAdapterConfig(
        run_id="r1",
        config_path=Path("/tmp/configs/run.yaml"),
        project_dir=project_dir,
        gpu_type="a10",
        modal_token_id="token-id",
        modal_token_secret="token-secret",
        heartbeat_path=Path("/tmp/heartbeat.json"),
    )
    return ModalTrainingAdapter(config=config)


def test_translate_workspace_path_rewrites_run_checkpoint_to_host(tmp_path: Path) -> None:
    raw = "/workspace/runs/r1/checkpoints/checkpoint-100"

    translated = translate_workspace_path(raw_path=raw, project_dir=tmp_path)

    assert translated == str(tmp_path / "runs/r1/checkpoints/checkpoint-100")


def test_translate_workspace_path_passes_through_non_workspace_paths(tmp_path: Path) -> None:
    assert (
        translate_workspace_path(raw_path="/data/foo.bin", project_dir=tmp_path)
        == "/data/foo.bin"
    )
    assert translate_workspace_path(raw_path="", project_dir=tmp_path) == ""
    assert (
        translate_workspace_path(raw_path="relative/path.json", project_dir=tmp_path)
        == "relative/path.json"
    )


def test_rewrite_event_paths_translates_checkpoint_event(tmp_path: Path) -> None:
    adapter = _make_adapter(project_dir=tmp_path)
    event: dict[str, object] = {
        "type": "checkpoint",
        "step": 100,
        "path": "/workspace/runs/r1/checkpoints/checkpoint-100",
        "size_bytes": 1024,
        "is_best_eval": False,
    }

    adapter._rewrite_event_paths(event=event)

    assert event["path"] == str(tmp_path / "runs/r1/checkpoints/checkpoint-100")


def test_rewrite_event_paths_translates_artifact_event(tmp_path: Path) -> None:
    adapter = _make_adapter(project_dir=tmp_path)
    event: dict[str, object] = {
        "type": "artifact",
        "artifact_type": "final_model",
        "path": "/workspace/runs/r1/artifacts/final_model",
        "size_bytes": 4096,
    }

    adapter._rewrite_event_paths(event=event)

    assert event["path"] == str(tmp_path / "runs/r1/artifacts/final_model")


def test_rewrite_event_paths_leaves_non_path_events_alone(tmp_path: Path) -> None:
    adapter = _make_adapter(project_dir=tmp_path)
    original: dict[str, object] = {
        "type": "metric",
        "metric_name": "train_loss",
        "value": 1.23,
        "step": 50,
    }
    event = dict(original)

    adapter._rewrite_event_paths(event=event)

    assert event == original


def test_rewrite_event_paths_tolerates_missing_or_non_string_path(tmp_path: Path) -> None:
    adapter = _make_adapter(project_dir=tmp_path)
    no_path: dict[str, object] = {"type": "checkpoint", "step": 1}
    adapter._rewrite_event_paths(event=no_path)
    assert "path" not in no_path

    non_string: dict[str, object] = {"type": "checkpoint", "path": 42}
    adapter._rewrite_event_paths(event=non_string)
    assert non_string["path"] == 42
