from __future__ import annotations

import json
from pathlib import Path

from app.cli.modal_smoke import _seed_sanitized_artifact


def test_seed_writes_sanitized_jsonl_and_manifest(tmp_path: Path) -> None:
    _seed_sanitized_artifact(project_dir=tmp_path)

    artifact = tmp_path / "datasets" / "sanitized.jsonl"
    manifest = tmp_path / "datasets" / "sanitized.meta.json"
    assert artifact.is_file()
    assert manifest.is_file()

    lines = artifact.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    # Smoke seed writes a flat prompt/response pair (normalize=false) so the
    # trainer's tokenization stage can read input_field/target_field directly.
    assert row["prompt"] == "modal smoke check"
    assert row["response"] == "ok"


def test_seed_manifest_carries_content_hash_total_rows_and_split_counts(
    tmp_path: Path,
) -> None:
    _seed_sanitized_artifact(project_dir=tmp_path)

    manifest = json.loads((tmp_path / "datasets" / "sanitized.meta.json").read_text())
    assert isinstance(manifest["content_hash"], str)
    assert len(manifest["content_hash"]) == 64
    assert manifest["total_rows"] == 1
    assert manifest["split_counts"] == {"train": 1, "val": 0, "test": 0}


def test_seed_leaves_no_tmp_files_after_atomic_write(tmp_path: Path) -> None:
    _seed_sanitized_artifact(project_dir=tmp_path)
    assert not list((tmp_path / "datasets").glob("*.tmp"))


def test_seeded_artifact_satisfies_build_modal_upload_plan(tmp_path: Path) -> None:
    from app.services.cloud.modal_adapter import build_modal_upload_plan

    config_path = tmp_path / "configs" / "smoke.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("execution:\n  environment: modal\n", encoding="utf-8")

    _seed_sanitized_artifact(project_dir=tmp_path)

    plan = build_modal_upload_plan(project_dir=tmp_path, config_path=config_path)
    artifact_paths = {local.name for local, _remote in plan.files}
    assert "sanitized.jsonl" in artifact_paths
    assert "sanitized.meta.json" in artifact_paths
