"""Tests for watchdog's atomic-checkpoint-aware resume selection (issue #33).

The watchdog is the single component that decides which checkpoint is
safe to resume from after a crash. It must skip `.tmp-checkpoint-*`
staging dirs AND fully-named `checkpoint-N` dirs that lack the COMPLETE
marker — those represent runs killed mid-save before the rank-0 commit.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services import watchdog


def _make_checkpoint(
    *, checkpoints_dir: Path, step: int, is_complete: bool, with_hf_config: bool
) -> Path:
    checkpoint_dir = checkpoints_dir / f"checkpoint-{step}"
    checkpoint_dir.mkdir(parents=True)
    (checkpoint_dir / "model.safetensors").write_bytes(b"stub-weights")
    if with_hf_config:
        (checkpoint_dir / "config.json").write_text("{}")
    if is_complete:
        (checkpoint_dir / watchdog._CHECKPOINT_COMPLETE_MARKER).write_text(
            json.dumps({"step": step})
        )
    return checkpoint_dir


def test_find_latest_valid_checkpoint_prefers_marker_over_missing(tmp_path: Path) -> None:
    run_id = "run-recov-1"
    checkpoints_dir = tmp_path / "runs" / run_id / "checkpoints"
    _make_checkpoint(
        checkpoints_dir=checkpoints_dir, step=10, is_complete=True, with_hf_config=False
    )
    _make_checkpoint(
        checkpoints_dir=checkpoints_dir, step=20, is_complete=False, with_hf_config=False
    )
    latest = watchdog._find_latest_valid_checkpoint(project_dir=tmp_path, run_id=run_id)
    assert latest is not None
    assert latest.endswith("checkpoint-10")


def test_find_latest_valid_checkpoint_accepts_legacy_hf_checkpoint(tmp_path: Path) -> None:
    run_id = "run-recov-2"
    checkpoints_dir = tmp_path / "runs" / run_id / "checkpoints"
    _make_checkpoint(
        checkpoints_dir=checkpoints_dir, step=5, is_complete=False, with_hf_config=True
    )
    latest = watchdog._find_latest_valid_checkpoint(project_dir=tmp_path, run_id=run_id)
    assert latest is not None
    assert latest.endswith("checkpoint-5")


def test_find_latest_valid_checkpoint_skips_partial_and_tmp(tmp_path: Path) -> None:
    run_id = "run-recov-3"
    checkpoints_dir = tmp_path / "runs" / run_id / "checkpoints"
    checkpoints_dir.mkdir(parents=True)
    tmp_dir = checkpoints_dir / ".tmp-checkpoint-99"
    tmp_dir.mkdir()
    (tmp_dir / "model.safetensors").write_bytes(b"half")
    _make_checkpoint(
        checkpoints_dir=checkpoints_dir, step=30, is_complete=False, with_hf_config=False
    )
    assert watchdog._find_latest_valid_checkpoint(project_dir=tmp_path, run_id=run_id) is None


def test_find_latest_valid_checkpoint_returns_highest_complete_step(tmp_path: Path) -> None:
    run_id = "run-recov-4"
    checkpoints_dir = tmp_path / "runs" / run_id / "checkpoints"
    _make_checkpoint(
        checkpoints_dir=checkpoints_dir, step=10, is_complete=True, with_hf_config=True
    )
    _make_checkpoint(
        checkpoints_dir=checkpoints_dir, step=40, is_complete=True, with_hf_config=True
    )
    _make_checkpoint(
        checkpoints_dir=checkpoints_dir, step=50, is_complete=False, with_hf_config=False
    )
    latest = watchdog._find_latest_valid_checkpoint(project_dir=tmp_path, run_id=run_id)
    assert latest is not None
    assert latest.endswith("checkpoint-40")


def test_clean_temp_checkpoints_removes_only_tmp_prefix(tmp_path: Path) -> None:
    run_id = "run-recov-5"
    checkpoints_dir = tmp_path / "runs" / run_id / "checkpoints"
    checkpoints_dir.mkdir(parents=True)
    tmp_dir = checkpoints_dir / ".tmp-checkpoint-99"
    tmp_dir.mkdir()
    (tmp_dir / "stub").write_bytes(b"x")
    good = _make_checkpoint(
        checkpoints_dir=checkpoints_dir, step=10, is_complete=True, with_hf_config=True
    )

    watchdog._clean_temp_checkpoints(project_dir=tmp_path, run_id=run_id)

    assert not tmp_dir.exists()
    assert good.exists()


def test_is_finalized_checkpoint_accepts_marker_without_hf_config(tmp_path: Path) -> None:
    checkpoint_dir = tmp_path / "checkpoint-7"
    checkpoint_dir.mkdir()
    (checkpoint_dir / watchdog._CHECKPOINT_COMPLETE_MARKER).write_text(json.dumps({"step": 7}))
    assert watchdog._is_finalized_checkpoint(checkpoint_dir) is True


def test_is_finalized_checkpoint_rejects_directory_with_only_weights(tmp_path: Path) -> None:
    checkpoint_dir = tmp_path / "checkpoint-11"
    checkpoint_dir.mkdir()
    (checkpoint_dir / "model.safetensors").write_bytes(b"partial")
    assert watchdog._is_finalized_checkpoint(checkpoint_dir) is False
