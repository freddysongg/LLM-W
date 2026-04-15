"""Source 200 stratified (prompt, output) calibration candidates from Dolly 15k.

Loads ``databricks/databricks-dolly-15k`` pinned to a specific dataset commit
SHA, stratifies across 10 domain buckets (Dolly's 6 single-category buckets
plus ``open_qa`` and ``general_qa`` each split into short/long sub-buckets by
instruction length), selects 20 examples per bucket deterministically via a
per-bucket ``random.Random(seed=42)`` shuffle, and writes:

  * ``eval/calibration/v1_raw.jsonl`` -- one JSON object per line, sorted by
    ``id``, serialized with sort_keys + ascii-only + tight separators.
  * ``eval/calibration/v1_raw.hash`` -- SHA256 of the jsonl file bytes
    (single line, 64 hex chars + trailing newline).

Determinism contract: re-running the script with the same pinned dataset
revision must produce byte-identical outputs. The script refuses to overwrite
mismatching outputs unless ``--force`` is passed.

The "output" field on each row is Dolly's reference ``response``. This is
intentional -- at label time the human will perturb ~30-40 percent of outputs
to inject realistic fail cases (see ``eval/calibration/README.md``).

Usage::

    python3 scripts/eval/source_calibration_set.py
    python3 scripts/eval/source_calibration_set.py --output-dir /tmp/cal
    python3 scripts/eval/source_calibration_set.py --force

"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

_STDERR_PREFIX = "[source-calibration]"

_DATASET_ID = "databricks/databricks-dolly-15k"
_DATASET_REVISION = "bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a"
_DATASET_SPLIT = "train"
_SHUFFLE_SEED = 42
_PER_BUCKET_TARGET = 20
_TOTAL_TARGET = 200
_ID_HASH_WIDTH = 8

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "eval" / "calibration"
_JSONL_FILENAME = "v1_raw.jsonl"
_HASH_FILENAME = "v1_raw.hash"

_CATEGORY_OPEN_QA = "open_qa"
_CATEGORY_GENERAL_QA = "general_qa"
_CATEGORIES_TO_SPLIT = frozenset({_CATEGORY_OPEN_QA, _CATEGORY_GENERAL_QA})
_CATEGORIES_SINGLE = (
    "brainstorming",
    "classification",
    "closed_qa",
    "creative_writing",
    "information_extraction",
    "summarization",
)

LengthBand = Literal["short", "long"]


class _DatasetRow(Protocol):
    def __getitem__(self, key: str) -> object: ...


@dataclass(frozen=True)
class SourceArgs:
    output_dir: Path
    force: bool


@dataclass(frozen=True)
class SourceResult:
    jsonl_path: Path
    hash_path: Path
    sha256: str
    example_count: int
    bucket_distribution: dict[str, int]


@dataclass(frozen=True)
class _CandidateRow:
    prompt: str
    output: str
    reference: str
    domain: str
    row_index: int


def _eprint(*, message: str) -> None:
    print(f"{_STDERR_PREFIX} {message}", file=sys.stderr, flush=True)


def _serialize_example(*, example: dict[str, object]) -> str:
    return json.dumps(example, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _compute_row_id(*, prompt: str, output: str) -> str:
    payload = json.dumps(
        {"prompt": prompt, "output": output},
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"cal-{digest[:_ID_HASH_WIDTH]}"


def _build_prompt(*, instruction: str, context: str) -> str:
    """Concatenate Dolly's instruction and context into a single prompt string.

    Dolly splits the user-facing request across ``instruction`` and an optional
    ``context`` passage. The calibration harness treats the prompt as one
    opaque string, so we reconstruct a natural-language user turn here.
    """
    instruction_trimmed = instruction.strip()
    context_trimmed = context.strip()
    if not context_trimmed:
        return instruction_trimmed
    return f"{instruction_trimmed}\n\nContext:\n{context_trimmed}"


def _assign_length_band(*, instruction_length: int, median_length: int) -> LengthBand:
    """Return ``short`` when instruction length <= median, else ``long``.

    Using ``<=`` against the median biases the ``short`` half to absorb the
    median tie so the bucket split is stable under recomputation.
    """
    if instruction_length <= median_length:
        return "short"
    return "long"


def _median_instruction_length(*, instructions: list[str]) -> int:
    if not instructions:
        raise RuntimeError("cannot compute median over empty instruction list")
    ordered = sorted(len(text) for text in instructions)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) // 2


def _domain_for_row(
    *, category: str, instruction_length: int, split_medians: dict[str, int]
) -> str:
    if category in _CATEGORIES_TO_SPLIT:
        band = _assign_length_band(
            instruction_length=instruction_length,
            median_length=split_medians[category],
        )
        return f"{category}_{band}"
    return category


def _bucket_candidates(*, rows: list[dict[str, object]]) -> dict[str, list[_CandidateRow]]:
    instructions_by_split_category: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        category = _coerce_str(value=row["category"], field="category")
        if category in _CATEGORIES_TO_SPLIT:
            instruction = _coerce_str(value=row["instruction"], field="instruction")
            instructions_by_split_category[category].append(instruction)

    split_medians: dict[str, int] = {
        category: _median_instruction_length(instructions=texts)
        for category, texts in instructions_by_split_category.items()
    }

    buckets: dict[str, list[_CandidateRow]] = defaultdict(list)
    for row_index, row in enumerate(rows):
        category = _coerce_str(value=row["category"], field="category")
        instruction = _coerce_str(value=row["instruction"], field="instruction")
        response = _coerce_str(value=row["response"], field="response")
        context = _coerce_str(value=row.get("context", ""), field="context")

        instruction_trimmed = instruction.strip()
        response_trimmed = response.strip()
        if not instruction_trimmed or not response_trimmed:
            continue

        domain = _domain_for_row(
            category=category,
            instruction_length=len(instruction),
            split_medians=split_medians,
        )
        prompt = _build_prompt(instruction=instruction, context=context)
        buckets[domain].append(
            _CandidateRow(
                prompt=prompt,
                output=response_trimmed,
                reference=response_trimmed,
                domain=domain,
                row_index=row_index,
            )
        )
    return buckets


def _coerce_str(*, value: object, field: str) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"expected string for Dolly field {field!r}, got {type(value).__name__}")
    return value


def _expected_bucket_names() -> list[str]:
    split_names = [
        f"{category}_{band}"
        for category in sorted(_CATEGORIES_TO_SPLIT)
        for band in ("long", "short")
    ]
    return sorted([*_CATEGORIES_SINGLE, *split_names])


def _select_stratified(*, buckets: dict[str, list[_CandidateRow]]) -> list[_CandidateRow]:
    expected = _expected_bucket_names()
    missing = [name for name in expected if name not in buckets]
    if missing:
        raise RuntimeError(
            f"dataset produced no candidates for buckets {missing!r}; "
            f"available buckets: {sorted(buckets.keys())}"
        )

    selected: list[_CandidateRow] = []
    deficits: dict[str, int] = {}
    for bucket_name in expected:
        candidates = sorted(buckets[bucket_name], key=lambda row: row.row_index)
        rng = random.Random(_SHUFFLE_SEED)
        shuffled = list(candidates)
        rng.shuffle(shuffled)
        take = shuffled[:_PER_BUCKET_TARGET]
        selected.extend(take)
        if len(take) < _PER_BUCKET_TARGET:
            deficits[bucket_name] = _PER_BUCKET_TARGET - len(take)

    if deficits:
        selected.extend(
            _fill_deficits_from_largest_buckets(
                buckets=buckets,
                already_selected=selected,
                deficit_count=sum(deficits.values()),
            )
        )

    if len(selected) != _TOTAL_TARGET:
        raise RuntimeError(
            f"stratified selection produced {len(selected)} rows, expected {_TOTAL_TARGET}"
        )
    return selected


def _fill_deficits_from_largest_buckets(
    *,
    buckets: dict[str, list[_CandidateRow]],
    already_selected: list[_CandidateRow],
    deficit_count: int,
) -> list[_CandidateRow]:
    """Pull extra rows from the largest buckets to compensate for undersized ones.

    Walks buckets in descending size order and skims additional candidates that
    were not already selected. Deterministic because each bucket is reshuffled
    with the same seed and we pick the earliest unselected rows in order.
    """
    selected_keys = {(row.domain, row.row_index) for row in already_selected}
    bucket_order = sorted(buckets.keys(), key=lambda name: (-len(buckets[name]), name))
    filler: list[_CandidateRow] = []
    remaining = deficit_count
    for bucket_name in bucket_order:
        if remaining <= 0:
            break
        candidates = sorted(buckets[bucket_name], key=lambda row: row.row_index)
        rng = random.Random(_SHUFFLE_SEED)
        shuffled = list(candidates)
        rng.shuffle(shuffled)
        for row in shuffled:
            if remaining <= 0:
                break
            key = (row.domain, row.row_index)
            if key in selected_keys:
                continue
            filler.append(row)
            selected_keys.add(key)
            remaining -= 1
    if remaining > 0:
        raise RuntimeError(f"could not fill {remaining} deficit rows after walking all buckets")
    return filler


def _load_dolly_rows() -> list[dict[str, object]]:
    try:
        from datasets import load_dataset  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "datasets is not importable; install with "
            "'pip install \"datasets>=2.0.0\"' before running this script."
        ) from exc

    dataset = load_dataset(_DATASET_ID, revision=_DATASET_REVISION)
    if _DATASET_SPLIT not in dataset:
        raise RuntimeError(
            f"dataset {_DATASET_ID}@{_DATASET_REVISION} has no split "
            f"{_DATASET_SPLIT!r}; available splits: {sorted(dataset.keys())}"
        )
    split = dataset[_DATASET_SPLIT]
    return [dict(row) for row in split]


def _row_to_envelope(*, row: _CandidateRow) -> dict[str, object]:
    row_id = _compute_row_id(prompt=row.prompt, output=row.output)
    return {
        "id": row_id,
        "prompt": row.prompt,
        "output": row.output,
        "reference": row.reference,
        "domain": row.domain,
        "source": {
            "dataset": _DATASET_ID,
            "revision": _DATASET_REVISION,
            "row_index": row.row_index,
        },
        "metadata": {},
    }


def _render_jsonl(*, selected: list[_CandidateRow]) -> bytes:
    envelopes = [_row_to_envelope(row=row) for row in selected]
    seen_ids: set[str] = set()
    for envelope in envelopes:
        envelope_id = envelope["id"]
        if not isinstance(envelope_id, str):
            raise RuntimeError("envelope id must be a string")
        if envelope_id in seen_ids:
            raise RuntimeError(
                f"duplicate calibration id {envelope_id!r}; increase "
                "_ID_HASH_WIDTH or deduplicate prompts."
            )
        seen_ids.add(envelope_id)
    sorted_envelopes = sorted(envelopes, key=lambda env: str(env["id"]))
    lines = [_serialize_example(example=env) for env in sorted_envelopes]
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


def _bucket_distribution(*, selected: list[_CandidateRow]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in selected:
        counts[row.domain] += 1
    return dict(sorted(counts.items()))


def _parse_args(*, argv: list[str]) -> SourceArgs:
    parser = argparse.ArgumentParser(
        prog="source_calibration_set.py",
        description=(
            f"Source {_TOTAL_TARGET} stratified calibration candidates from "
            f"{_DATASET_ID}@{_DATASET_REVISION[:12]}..."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            f"Directory to write {_JSONL_FILENAME} and {_HASH_FILENAME}. "
            "Defaults to eval/calibration/ under the repo root."
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
    output_dir = Path(parsed.output_dir).resolve() if parsed.output_dir else _DEFAULT_OUTPUT_DIR
    return SourceArgs(output_dir=output_dir, force=bool(parsed.force))


def source_calibration(*, args: SourceArgs) -> SourceResult:
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rows = _load_dolly_rows()
    buckets = _bucket_candidates(rows=rows)
    selected = _select_stratified(buckets=buckets)

    jsonl_path = args.output_dir / _JSONL_FILENAME
    hash_path = args.output_dir / _HASH_FILENAME

    jsonl_bytes = _render_jsonl(selected=selected)
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

    return SourceResult(
        jsonl_path=jsonl_path,
        hash_path=hash_path,
        sha256=sha256,
        example_count=len(selected),
        bucket_distribution=_bucket_distribution(selected=selected),
    )


def run(*, argv: list[str]) -> int:
    try:
        args = _parse_args(argv=argv)
    except SystemExit as exit_exc:
        return int(exit_exc.code or 0)

    try:
        result = source_calibration(args=args)
    except RuntimeError as exc:
        _eprint(message=str(exc))
        return 1

    print(f"wrote {result.example_count} examples to {result.jsonl_path}")
    print(f"wrote sha256 to {result.hash_path}")
    print(f"sha256: {result.sha256}")
    print(f"bucket distribution: {result.bucket_distribution}")
    return 0


def main() -> int:
    return run(argv=sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
