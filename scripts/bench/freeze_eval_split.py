"""Freeze a deterministic 200-example held-out eval split for the bench harness.

Loads ``HuggingFaceH4/ultrachat_200k`` pinned to a specific dataset commit
SHA, materializes a 200-example slice that is provably disjoint from the
2000-example training subset used by ``configs/bench/qwen15b-lora.yaml``,
and writes:

  * ``configs/bench/eval_split.jsonl`` — one JSON object per line, sorted by
    ``prompt_id``, serialized with sort_keys + ascii-only + tight separators.
  * ``configs/bench/eval_split.hash`` — SHA256 of the jsonl file bytes
    (single line, 64 hex chars + trailing newline).

Determinism contract: re-running the script with the same pinned dataset
revision must produce byte-identical outputs. The script refuses to
overwrite mismatching outputs unless ``--force`` is passed.

Usage::

    python3 scripts/bench/freeze_eval_split.py
    python3 scripts/bench/freeze_eval_split.py --output-dir /tmp/freeze
    python3 scripts/bench/freeze_eval_split.py --force

"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

_STDERR_PREFIX = "[freeze]"

_DATASET_ID = "HuggingFaceH4/ultrachat_200k"
_DATASET_REVISION = "8049631c405ae6576f93f445c6b8166f76f5505a"
_TRAIN_SPLIT = "train_sft"
_SHUFFLE_SEED = 42
_TRAIN_SUBSET_SIZE = 2000
_EVAL_SUBSET_SIZE = 200
_EVAL_SLICE_START = _TRAIN_SUBSET_SIZE
_EVAL_SLICE_STOP = _TRAIN_SUBSET_SIZE + _EVAL_SUBSET_SIZE
_SORT_KEY_FIELD = "prompt_id"

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "configs" / "bench"
_JSONL_FILENAME = "eval_split.jsonl"
_HASH_FILENAME = "eval_split.hash"


@dataclass(frozen=True)
class FreezeArgs:
    output_dir: Path
    force: bool


@dataclass(frozen=True)
class FreezeResult:
    jsonl_path: Path
    hash_path: Path
    sha256: str
    example_count: int


def _eprint(message: str) -> None:
    print(f"{_STDERR_PREFIX} {message}", file=sys.stderr, flush=True)


def _serialize_example(*, example: dict[str, object]) -> str:
    return json.dumps(example, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _stable_sort_key(*, example: dict[str, object]) -> str:
    """Return a per-example sort key used to lock row order in the output file.

    Prefers the dataset's own ``prompt_id`` field when present (ultrachat_200k
    rows include it) so the sort order is human-meaningful. Falls back to a
    SHA256 of the deterministic JSON serialization so the script still works
    on stub datasets in tests that omit the field.
    """
    candidate = example.get(_SORT_KEY_FIELD)
    if isinstance(candidate, str) and candidate:
        return f"id:{candidate}"
    payload = _serialize_example(example=example).encode("utf-8")
    return f"hash:{hashlib.sha256(payload).hexdigest()}"


def _load_eval_examples() -> list[dict[str, object]]:
    """Load the pinned ultrachat_200k split and return the held-out 200 rows."""
    try:
        from datasets import load_dataset  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "datasets is not importable; install with "
            "'pip install \"datasets>=2.0.0\"' before running this script."
        ) from exc

    dataset = load_dataset(_DATASET_ID, revision=_DATASET_REVISION)
    if _TRAIN_SPLIT not in dataset:
        raise RuntimeError(
            f"dataset {_DATASET_ID}@{_DATASET_REVISION} has no split {_TRAIN_SPLIT!r}; "
            f"available splits: {sorted(dataset.keys())}"
        )

    train_split = dataset[_TRAIN_SPLIT]
    total_rows = len(train_split)
    if total_rows < _EVAL_SLICE_STOP:
        raise RuntimeError(
            f"split {_TRAIN_SPLIT!r} has only {total_rows} rows; "
            f"need at least {_EVAL_SLICE_STOP} to carve out a disjoint eval slice."
        )

    shuffled = train_split.shuffle(seed=_SHUFFLE_SEED)
    eval_slice = shuffled.select(range(_EVAL_SLICE_START, _EVAL_SLICE_STOP))
    return [dict(row) for row in eval_slice]


def _render_jsonl(*, examples: list[dict[str, object]]) -> bytes:
    sorted_examples = sorted(examples, key=lambda row: _stable_sort_key(example=row))
    lines = [_serialize_example(example=row) for row in sorted_examples]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _render_hash_file(*, jsonl_bytes: bytes) -> tuple[str, bytes]:
    sha256 = hashlib.sha256(jsonl_bytes).hexdigest()
    return sha256, (sha256 + "\n").encode("utf-8")


def _write_atomically(*, destination: Path, payload: bytes) -> None:
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    tmp_path.write_bytes(payload)
    tmp_path.replace(destination)


def _check_drift(*, destination: Path, payload: bytes) -> bool:
    if not destination.exists():
        return False
    return destination.read_bytes() != payload


def _parse_args(*, argv: list[str]) -> FreezeArgs:
    parser = argparse.ArgumentParser(
        prog="freeze_eval_split.py",
        description=(
            "Freeze a deterministic 200-example held-out eval split from "
            f"{_DATASET_ID}@{_DATASET_REVISION[:12]}…"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Directory to write eval_split.jsonl and eval_split.hash. "
            "Defaults to configs/bench/ under the repo root."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Overwrite existing outputs even if they differ from the freshly "
            "generated content. Without this flag the script exits non-zero "
            "on drift."
        ),
    )
    parsed = parser.parse_args(argv)
    output_dir = (
        Path(parsed.output_dir).resolve() if parsed.output_dir else _DEFAULT_OUTPUT_DIR
    )
    return FreezeArgs(output_dir=output_dir, force=bool(parsed.force))


def freeze(*, args: FreezeArgs) -> FreezeResult:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    examples = _load_eval_examples()
    if len(examples) != _EVAL_SUBSET_SIZE:
        raise RuntimeError(
            f"expected {_EVAL_SUBSET_SIZE} eval examples, got {len(examples)}"
        )

    jsonl_path = args.output_dir / _JSONL_FILENAME
    hash_path = args.output_dir / _HASH_FILENAME

    jsonl_bytes = _render_jsonl(examples=examples)
    sha256, hash_bytes = _render_hash_file(jsonl_bytes=jsonl_bytes)

    jsonl_drift = _check_drift(destination=jsonl_path, payload=jsonl_bytes)
    hash_drift = _check_drift(destination=hash_path, payload=hash_bytes)
    if (jsonl_drift or hash_drift) and not args.force:
        raise RuntimeError(
            f"on-disk outputs differ from regenerated content "
            f"(jsonl_drift={jsonl_drift}, hash_drift={hash_drift}); "
            "rerun with --force to overwrite."
        )

    _write_atomically(destination=jsonl_path, payload=jsonl_bytes)
    _write_atomically(destination=hash_path, payload=hash_bytes)

    return FreezeResult(
        jsonl_path=jsonl_path,
        hash_path=hash_path,
        sha256=sha256,
        example_count=len(examples),
    )


def run(*, argv: list[str]) -> int:
    try:
        args = _parse_args(argv=argv)
    except SystemExit as exit_exc:
        return int(exit_exc.code or 0)

    try:
        result = freeze(args=args)
    except RuntimeError as exc:
        _eprint(str(exc))
        return 1

    print(f"wrote {result.example_count} examples to {result.jsonl_path}")
    print(f"wrote sha256 to {result.hash_path}")
    print(f"sha256: {result.sha256}")
    return 0


def main() -> int:
    return run(argv=sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
