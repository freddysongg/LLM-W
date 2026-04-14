"""Tests for scripts/bench/freeze_eval_split.py.

The real run requires HuggingFace network access and downloads ~1 GB of
parquet shards, which is unsuitable for unit tests. These tests stub
``datasets.load_dataset`` with a synthetic in-memory dataset that mimics the
relevant shape (a mapping of split-name → indexable rows that supports
``shuffle(seed=...).select(range(...))``).

The stub guarantees:
  * Determinism: re-shuffling with the same seed returns the same row order.
  * Disjointness: the eval slice [2000, 2200) cannot overlap with the train
    subset [0, 2000) because both come from one shuffled sequence.

The committed-output integrity tests live in ``test_run_local.py`` so they
share the runner's existing fixture style.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Iterable
from pathlib import Path

import pytest

_SCRIPTS_BENCH_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPTS_BENCH_DIR))

import freeze_eval_split  # noqa: E402

_TOTAL_STUB_ROWS = 2400


class _StubSplit:
    """In-memory analog of a `datasets.Dataset` for one split."""

    def __init__(self, *, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def __len__(self) -> int:
        return len(self._rows)

    def shuffle(self, *, seed: int) -> _StubSplit:
        import random  # noqa: PLC0415

        rng = random.Random(seed)
        shuffled = list(self._rows)
        rng.shuffle(shuffled)
        return _StubSplit(rows=shuffled)

    def select(self, indices: Iterable[int]) -> _StubSplit:
        index_list = list(indices)
        return _StubSplit(rows=[self._rows[i] for i in index_list])

    def __iter__(self) -> object:
        return iter(self._rows)


class _StubDatasetDict(dict[str, _StubSplit]):
    pass


def _build_stub_dataset(*, total_rows: int) -> _StubDatasetDict:
    rows: list[dict[str, object]] = [
        {
            "prompt_id": f"id-{idx:06d}",
            "prompt": f"prompt {idx}",
            "messages": [{"role": "user", "content": f"msg {idx}"}],
        }
        for idx in range(total_rows)
    ]
    dataset = _StubDatasetDict()
    dataset["train_sft"] = _StubSplit(rows=rows)
    return dataset


@pytest.fixture
def patched_load_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace `datasets.load_dataset` with the stub for the freeze script."""
    import datasets  # noqa: PLC0415

    def _fake_load(dataset_id: str, revision: str | None = None) -> _StubDatasetDict:
        assert dataset_id == "HuggingFaceH4/ultrachat_200k"
        assert revision == freeze_eval_split._DATASET_REVISION
        return _build_stub_dataset(total_rows=_TOTAL_STUB_ROWS)

    monkeypatch.setattr(datasets, "load_dataset", _fake_load)


def test_freeze_writes_expected_file_count(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    args = freeze_eval_split.FreezeArgs(output_dir=tmp_path, force=False)
    result = freeze_eval_split.freeze(args=args)
    assert result.example_count == 200
    lines = result.jsonl_path.read_text().splitlines()
    assert len(lines) == 200


def test_freeze_is_byte_identical_across_runs(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    freeze_eval_split.freeze(
        args=freeze_eval_split.FreezeArgs(output_dir=out_a, force=False)
    )
    freeze_eval_split.freeze(
        args=freeze_eval_split.FreezeArgs(output_dir=out_b, force=False)
    )
    assert (out_a / "eval_split.jsonl").read_bytes() == (
        out_b / "eval_split.jsonl"
    ).read_bytes()
    assert (out_a / "eval_split.hash").read_bytes() == (
        out_b / "eval_split.hash"
    ).read_bytes()


def test_freeze_hash_file_matches_jsonl_sha256(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    result = freeze_eval_split.freeze(
        args=freeze_eval_split.FreezeArgs(output_dir=tmp_path, force=False)
    )
    expected = hashlib.sha256(result.jsonl_path.read_bytes()).hexdigest()
    on_disk_hash = result.hash_path.read_text().strip()
    assert on_disk_hash == expected
    assert result.sha256 == expected


def test_freeze_eval_slice_is_disjoint_from_train_subset(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    """Verify the eval slice indices [2000, 2200) cannot overlap with [0, 2000)."""
    result = freeze_eval_split.freeze(
        args=freeze_eval_split.FreezeArgs(output_dir=tmp_path, force=False)
    )
    eval_ids = {
        json.loads(line)["prompt_id"]
        for line in result.jsonl_path.read_text().splitlines()
    }

    import random  # noqa: PLC0415

    rng = random.Random(freeze_eval_split._SHUFFLE_SEED)
    indices = list(range(_TOTAL_STUB_ROWS))
    rng.shuffle(indices)
    train_indices = set(indices[: freeze_eval_split._TRAIN_SUBSET_SIZE])
    train_ids = {f"id-{i:06d}" for i in train_indices}
    assert eval_ids.isdisjoint(train_ids)
    assert len(eval_ids) == 200


def test_freeze_refuses_to_overwrite_drift_without_force(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    args = freeze_eval_split.FreezeArgs(output_dir=tmp_path, force=False)
    freeze_eval_split.freeze(args=args)
    (tmp_path / "eval_split.jsonl").write_bytes(b"tampered\n")
    with pytest.raises(RuntimeError, match="differ from regenerated content"):
        freeze_eval_split.freeze(args=args)


def test_freeze_overwrites_drift_with_force(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    freeze_eval_split.freeze(
        args=freeze_eval_split.FreezeArgs(output_dir=tmp_path, force=False)
    )
    (tmp_path / "eval_split.jsonl").write_bytes(b"tampered\n")
    forced = freeze_eval_split.freeze(
        args=freeze_eval_split.FreezeArgs(output_dir=tmp_path, force=True)
    )
    assert (tmp_path / "eval_split.jsonl").read_bytes() != b"tampered\n"
    assert forced.example_count == 200


def test_freeze_jsonl_lines_sorted_by_prompt_id(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    result = freeze_eval_split.freeze(
        args=freeze_eval_split.FreezeArgs(output_dir=tmp_path, force=False)
    )
    prompt_ids = [
        json.loads(line)["prompt_id"]
        for line in result.jsonl_path.read_text().splitlines()
    ]
    assert prompt_ids == sorted(prompt_ids)


def test_freeze_serialization_uses_sort_keys_and_no_spaces(
    tmp_path: Path, patched_load_dataset: None
) -> None:
    result = freeze_eval_split.freeze(
        args=freeze_eval_split.FreezeArgs(output_dir=tmp_path, force=False)
    )
    first_line = result.jsonl_path.read_text().splitlines()[0]
    assert ", " not in first_line
    assert ": " not in first_line
    parsed = json.loads(first_line)
    keys = list(parsed.keys())
    assert keys == sorted(keys)
