"""Tests for scripts/eval/source_calibration_set.py.

The real run requires HuggingFace network access. These tests stub
``datasets.load_dataset`` with a synthetic in-memory dataset that mimics
Dolly's shape (rows with ``instruction``, ``context``, ``response``,
``category`` fields) plus a ``train`` split. The stub provides at least 30
rows per category so every bucket has enough candidates to hit the
per-bucket target of 20.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "eval" / "source_calibration_set.py"


def _load_source_calibration_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("source_calibration_set", _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module from {_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["source_calibration_set"] = module
    spec.loader.exec_module(module)
    return module


source_calibration_set = _load_source_calibration_module()


_DOLLY_CATEGORIES_SINGLE = (
    "brainstorming",
    "classification",
    "closed_qa",
    "creative_writing",
    "information_extraction",
    "summarization",
)
_DOLLY_CATEGORIES_SPLIT = ("open_qa", "general_qa")
_ROWS_PER_CATEGORY = 60


class _StubSplit:
    def __init__(self, *, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def __len__(self) -> int:
        return len(self._rows)

    def __iter__(self) -> Iterable[dict[str, object]]:
        return iter(self._rows)

    def __getitem__(self, index: int) -> dict[str, object]:
        return self._rows[index]


class _StubDatasetDict(dict[str, _StubSplit]):
    pass


def _build_stub_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for category in _DOLLY_CATEGORIES_SINGLE:
        for seq in range(_ROWS_PER_CATEGORY):
            instruction = f"{category} instruction number {seq} with some filler text"
            context = f"context-for-{category}-{seq}" if category == "closed_qa" else ""
            if category == "summarization":
                context = f"document body used for summarization row {seq}"
            if category == "information_extraction":
                context = f"passage for extraction {seq}"
            rows.append(
                {
                    "instruction": instruction,
                    "context": context,
                    "response": f"reference answer to {category} row {seq}",
                    "category": category,
                }
            )
    for category in _DOLLY_CATEGORIES_SPLIT:
        for seq in range(_ROWS_PER_CATEGORY):
            is_long = seq % 2 == 0
            if is_long:
                instruction = (
                    f"{category} long-form instruction number {seq} "
                    "padded with additional words to exceed the median"
                )
            else:
                instruction = f"{category} q{seq}"
            rows.append(
                {
                    "instruction": instruction,
                    "context": "",
                    "response": f"reference answer to {category} row {seq}",
                    "category": category,
                }
            )
    return rows


@pytest.fixture
def patched_load_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    import datasets

    def _fake_load(dataset_id: str, revision: str | None = None) -> _StubDatasetDict:
        assert dataset_id == source_calibration_set._DATASET_ID
        assert revision == source_calibration_set._DATASET_REVISION
        dataset = _StubDatasetDict()
        dataset["train"] = _StubSplit(rows=_build_stub_rows())
        return dataset

    monkeypatch.setattr(datasets, "load_dataset", _fake_load)


def _read_jsonl_rows(*, path: Path) -> list[dict[str, object]]:
    return [cast(dict[str, object], json.loads(line)) for line in path.read_text().splitlines()]


def test_source_script_writes_exactly_200_rows(tmp_path: Path, patched_load_dataset: None) -> None:
    args = source_calibration_set.SourceArgs(output_dir=tmp_path, force=False)
    result = source_calibration_set.source_calibration(args=args)
    assert result.example_count == 200
    lines = result.jsonl_path.read_text().splitlines()
    assert len(lines) == 200


def test_source_script_is_deterministic(tmp_path: Path, patched_load_dataset: None) -> None:
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    source_calibration_set.source_calibration(
        args=source_calibration_set.SourceArgs(output_dir=out_a, force=False)
    )
    source_calibration_set.source_calibration(
        args=source_calibration_set.SourceArgs(output_dir=out_b, force=False)
    )
    assert (out_a / "v1_raw.jsonl").read_bytes() == (out_b / "v1_raw.jsonl").read_bytes()
    assert (out_a / "v1_raw.hash").read_bytes() == (out_b / "v1_raw.hash").read_bytes()


def test_source_script_stratifies_across_at_least_10_domains(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    result = source_calibration_set.source_calibration(
        args=source_calibration_set.SourceArgs(output_dir=tmp_path, force=False)
    )
    rows = _read_jsonl_rows(path=result.jsonl_path)
    domains = {str(row["domain"]) for row in rows}
    assert len(domains) >= 10


def test_source_script_id_is_deterministic_per_prompt_output(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    result_a = source_calibration_set.source_calibration(
        args=source_calibration_set.SourceArgs(output_dir=tmp_path / "a", force=False)
    )
    result_b = source_calibration_set.source_calibration(
        args=source_calibration_set.SourceArgs(output_dir=tmp_path / "b", force=False)
    )
    rows_a = {row["id"]: row for row in _read_jsonl_rows(path=result_a.jsonl_path)}
    rows_b = {row["id"]: row for row in _read_jsonl_rows(path=result_b.jsonl_path)}
    assert rows_a.keys() == rows_b.keys()
    for row_id, row_a in rows_a.items():
        row_b = rows_b[row_id]
        assert row_a["prompt"] == row_b["prompt"]
        assert row_a["output"] == row_b["output"]
        expected_id = source_calibration_set._compute_row_id(
            prompt=cast(str, row_a["prompt"]),
            output=cast(str, row_a["output"]),
        )
        assert row_id == expected_id


def test_source_script_writes_hash_matching_jsonl(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    result = source_calibration_set.source_calibration(
        args=source_calibration_set.SourceArgs(output_dir=tmp_path, force=False)
    )
    expected = hashlib.sha256(result.jsonl_path.read_bytes()).hexdigest()
    on_disk_hash = result.hash_path.read_text().strip()
    assert on_disk_hash == expected
    assert result.sha256 == expected


def test_source_script_idempotent_overwrite_blocked_without_force(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    args = source_calibration_set.SourceArgs(output_dir=tmp_path, force=False)
    source_calibration_set.source_calibration(args=args)
    original_jsonl = (tmp_path / "v1_raw.jsonl").read_bytes()
    (tmp_path / "v1_raw.jsonl").write_bytes(b"tampered\n")
    with pytest.raises(RuntimeError, match="differ from regenerated content"):
        source_calibration_set.source_calibration(args=args)
    assert (tmp_path / "v1_raw.jsonl").read_bytes() == b"tampered\n"
    assert original_jsonl != b"tampered\n"


def test_source_script_force_regenerates(tmp_path: Path, patched_load_dataset: None) -> None:
    first = source_calibration_set.source_calibration(
        args=source_calibration_set.SourceArgs(output_dir=tmp_path, force=False)
    )
    original_bytes = first.jsonl_path.read_bytes()
    first.jsonl_path.unlink()
    first.hash_path.unlink()
    regenerated = source_calibration_set.source_calibration(
        args=source_calibration_set.SourceArgs(output_dir=tmp_path, force=True)
    )
    assert regenerated.jsonl_path.read_bytes() == original_bytes
    assert regenerated.sha256 == first.sha256


def test_source_script_bucket_distribution_is_balanced(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    result = source_calibration_set.source_calibration(
        args=source_calibration_set.SourceArgs(output_dir=tmp_path, force=False)
    )
    assert sum(result.bucket_distribution.values()) == 200
    assert all(count == 20 for count in result.bucket_distribution.values())


def test_source_script_output_sorted_by_id(tmp_path: Path, patched_load_dataset: None) -> None:
    result = source_calibration_set.source_calibration(
        args=source_calibration_set.SourceArgs(output_dir=tmp_path, force=False)
    )
    ids = [str(row["id"]) for row in _read_jsonl_rows(path=result.jsonl_path)]
    assert ids == sorted(ids)


def test_source_script_serialization_uses_tight_separators(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    result = source_calibration_set.source_calibration(
        args=source_calibration_set.SourceArgs(output_dir=tmp_path, force=False)
    )
    first_line = result.jsonl_path.read_text().splitlines()[0]
    assert ", " not in first_line
    assert ": " not in first_line
    parsed = json.loads(first_line)
    assert list(parsed.keys()) == sorted(parsed.keys())


def test_source_script_envelope_has_required_fields(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    result = source_calibration_set.source_calibration(
        args=source_calibration_set.SourceArgs(output_dir=tmp_path, force=False)
    )
    rows = _read_jsonl_rows(path=result.jsonl_path)
    required_fields = {
        "id",
        "prompt",
        "output",
        "reference",
        "domain",
        "source",
        "metadata",
    }
    for row in rows:
        assert required_fields.issubset(row.keys())
        source_block = cast(dict[str, object], row["source"])
        assert source_block["dataset"] == source_calibration_set._DATASET_ID
        assert source_block["revision"] == source_calibration_set._DATASET_REVISION
        assert isinstance(source_block["row_index"], int)
        assert cast(str, row["id"]).startswith("cal-")
