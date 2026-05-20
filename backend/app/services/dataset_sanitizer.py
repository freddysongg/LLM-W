from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.core.exceptions import DatasetNormalizationError
from app.schemas.dataset_sanitizer import (
    RedactionManifest,
    RedactionPattern,
    SanitizationResult,
    SanitizationRules,
    SanitizeDatasetRequest,
    SanitizeDatasetResponse,
    SourceFormat,
    SplitAssignment,
    SplitName,
    SplitRatios,
)


@dataclass(frozen=True)
class SanitizeArtifactStatus:
    exists: bool
    content_hash: str | None
    sanitized_at: str | None

PERSISTED_DATASET_FILENAME = "sanitized.jsonl"
PERSISTED_MANIFEST_FILENAME = "sanitized.meta.json"

DEFAULT_REDACTION_PATTERNS: list[RedactionPattern] = [
    RedactionPattern(
        name="email",
        regex=r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}",
        replacement="[REDACTED_EMAIL]",
    ),
    RedactionPattern(
        name="us_phone",
        regex=r"(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}",
        replacement="[REDACTED_PHONE]",
    ),
    RedactionPattern(
        name="credit_card",
        regex=r"\b(?:\d[ -]*?){13,16}\b",
        replacement="[REDACTED_CARD]",
    ),
    RedactionPattern(
        name="ssn",
        regex=r"\b\d{3}-\d{2}-\d{4}\b",
        replacement="[REDACTED_SSN]",
    ),
    RedactionPattern(
        name="ipv4",
        regex=r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
        replacement="[REDACTED_IP]",
    ),
]

_HASH_PREFIX_HEX_DIGITS = 8
_HASH_PREFIX_MODULUS = 1000


def default_sanitization_rules() -> SanitizationRules:
    """Return a fresh copy of the default redaction rule set."""
    return SanitizationRules(patterns=list(DEFAULT_REDACTION_PATTERNS))


def _compile_patterns(rules: SanitizationRules) -> list[tuple[str, re.Pattern[str], str]]:
    compiled: list[tuple[str, re.Pattern[str], str]] = []
    for pattern in rules.patterns:
        compiled.append((pattern.name, re.compile(pattern.regex), pattern.replacement))
    return compiled


def _redact_string(
    *,
    text: str,
    compiled: list[tuple[str, re.Pattern[str], str]],
    counts: dict[str, int],
) -> str:
    redacted = text
    for name, regex, replacement in compiled:
        matches = regex.findall(redacted)
        if matches:
            counts[name] = counts.get(name, 0) + len(matches)
            redacted = regex.sub(replacement, redacted)
    return redacted


def _redact_value(
    *,
    value: object,
    compiled: list[tuple[str, re.Pattern[str], str]],
    counts: dict[str, int],
) -> object:
    if isinstance(value, str):
        return _redact_string(text=value, compiled=compiled, counts=counts)
    if isinstance(value, list):
        return [_redact_value(value=item, compiled=compiled, counts=counts) for item in value]
    if isinstance(value, dict):
        return {
            key: _redact_value(value=inner_value, compiled=compiled, counts=counts)
            for key, inner_value in value.items()
        }
    return value


def _compute_content_hash(rows: list[dict[str, object]]) -> str:
    serialized = json.dumps(rows, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def sanitize_rows(
    *,
    rows: list[dict[str, object]],
    rules: SanitizationRules,
) -> SanitizationResult:
    """Walk rows recursively, redact every string match, return sanitized rows + manifest."""
    compiled = _compile_patterns(rules)
    counts: dict[str, int] = {pattern.name: 0 for pattern in rules.patterns}

    sanitized_rows: list[dict[str, object]] = []
    for row in rows:
        sanitized_value = _redact_value(value=row, compiled=compiled, counts=counts)
        if not isinstance(sanitized_value, dict):
            raise DatasetNormalizationError(
                "sanitize_rows expects each row to be a mapping at the top level"
            )
        sanitized_rows.append(sanitized_value)

    total = sum(counts.values())
    manifest = RedactionManifest(per_pattern=counts, total_redactions=total)
    content_hash = _compute_content_hash(sanitized_rows)
    return SanitizationResult(
        sanitized_rows=sanitized_rows,
        manifest=manifest,
        content_hash=content_hash,
    )


def _hash_row_to_unit_interval(row: dict[str, object]) -> float:
    serialized = json.dumps(row, sort_keys=True, default=str)
    digest_hex = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    prefix = digest_hex[:_HASH_PREFIX_HEX_DIGITS]
    return (int(prefix, 16) % _HASH_PREFIX_MODULUS) / _HASH_PREFIX_MODULUS


def _bucket_for(*, fraction: float, ratios: SplitRatios) -> SplitName:
    train_cut = ratios.train
    val_cut = ratios.train + ratios.val
    if fraction < train_cut:
        return "train"
    if fraction < val_cut:
        return "val"
    return "test"


def compute_deterministic_splits(
    *,
    rows: list[dict[str, object]],
    ratios: SplitRatios,
    seed_field: str = "_content_hash",
) -> SplitAssignment:
    """Assign each row to train/val/test using a hash of its content (stable across runs).

    `seed_field` is accepted for API compatibility and stored on copies that bear that
    key (e.g., outputs of `sanitize_rows`), but the underlying assignment is always
    derived from the deterministic hash of the row contents so the same input produces
    the same split regardless of whether `seed_field` is present.
    """
    assignments: dict[int, SplitName] = {}
    counts: dict[str, int] = {"train": 0, "val": 0, "test": 0}

    for index, row in enumerate(rows):
        if seed_field in row and isinstance(row[seed_field], str):
            digest_hex = str(row[seed_field])
            prefix = digest_hex[:_HASH_PREFIX_HEX_DIGITS]
            try:
                fraction = (int(prefix, 16) % _HASH_PREFIX_MODULUS) / _HASH_PREFIX_MODULUS
            except ValueError:
                fraction = _hash_row_to_unit_interval(row)
        else:
            fraction = _hash_row_to_unit_interval(row)
        bucket: SplitName = _bucket_for(fraction=fraction, ratios=ratios)
        assignments[index] = bucket
        counts[bucket] += 1

    return SplitAssignment(assignments=assignments, counts=counts)


def _wrap_default_messages(*, row: dict[str, object]) -> dict[str, object]:
    """Heuristic mapping for rows that don't match any of the known formats."""
    input_text = row.get("prompt") or row.get("input")
    output_text = row.get("response") or row.get("output") or row.get("completion")
    if not isinstance(input_text, str) or not isinstance(output_text, str):
        raise DatasetNormalizationError(
            "default format requires recognizable prompt/response fields, found neither"
        )
    return {
        "messages": [
            {"role": "user", "content": input_text},
            {"role": "assistant", "content": output_text},
        ]
    }


def _normalize_openai(*, row: dict[str, object]) -> dict[str, object]:
    if "messages" in row and isinstance(row["messages"], list):
        return row
    return _wrap_default_messages(row=row)


def _normalize_sharegpt(*, row: dict[str, object]) -> dict[str, object]:
    conversations = row.get("conversations")
    if not isinstance(conversations, list):
        raise DatasetNormalizationError("sharegpt format requires a 'conversations' list field")
    messages: list[dict[str, object]] = []
    for turn in conversations:
        if not isinstance(turn, dict):
            raise DatasetNormalizationError(
                "sharegpt conversation entries must be objects with 'from' and 'value'"
            )
        sender = turn.get("from")
        content = turn.get("value")
        if not isinstance(sender, str) or not isinstance(content, str):
            raise DatasetNormalizationError(
                "sharegpt conversation entries must have string 'from' and 'value'"
            )
        if sender == "human":
            role: Literal["user", "assistant", "system"] = "user"
        elif sender == "gpt":
            role = "assistant"
        elif sender == "system":
            role = "system"
        else:
            raise DatasetNormalizationError(
                f"sharegpt sender '{sender}' is not recognized (expected human/gpt/system)"
            )
        messages.append({"role": role, "content": content})
    return {"messages": messages}


def _normalize_alpaca(*, row: dict[str, object]) -> dict[str, object]:
    instruction = row.get("instruction")
    input_text = row.get("input", "")
    output_text = row.get("output")
    if not isinstance(instruction, str) or not isinstance(output_text, str):
        raise DatasetNormalizationError(
            "alpaca format requires string 'instruction' and 'output' fields"
        )
    if not isinstance(input_text, str):
        raise DatasetNormalizationError("alpaca 'input' field must be a string when present")

    user_content = instruction
    if input_text:
        user_content = f"{instruction} {input_text}"
    return {
        "messages": [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": output_text},
        ]
    }


def normalize_to_openai_messages(
    *,
    row: dict[str, object],
    source_format: SourceFormat,
) -> dict[str, object]:
    """Convert a row from its source format to the canonical OpenAI messages shape."""
    if source_format == "openai":
        return _normalize_openai(row=row)
    if source_format == "sharegpt":
        return _normalize_sharegpt(row=row)
    if source_format == "alpaca":
        return _normalize_alpaca(row=row)
    if source_format == "default":
        return _wrap_default_messages(row=row)

    raise DatasetNormalizationError(f"unsupported source_format: {source_format}")


def run_sanitization_pipeline(
    *,
    rows: list[dict[str, object]],
    request: SanitizeDatasetRequest,
) -> SanitizeDatasetResponse:
    """Apply redaction, optional normalization, and deterministic splitting in one pass."""
    rules = request.rules or default_sanitization_rules()
    sanitized = sanitize_rows(rows=rows, rules=rules)

    if request.normalize:
        normalized_rows = [
            normalize_to_openai_messages(row=row, source_format=request.source_format)
            for row in sanitized.sanitized_rows
        ]
        # Recompute the hash over the rows that actually get persisted —
        # otherwise the Modal upload-skip check would treat a normalized
        # artifact and its pre-normalized counterpart as identical and reuse
        # a stale remote file when only the row shape changed.
        artifact_content_hash = _compute_content_hash(normalized_rows)
    else:
        normalized_rows = sanitized.sanitized_rows
        artifact_content_hash = sanitized.content_hash

    splits = compute_deterministic_splits(rows=normalized_rows, ratios=request.split_ratios)

    return SanitizeDatasetResponse(
        total_rows=len(normalized_rows),
        sanitized_rows=normalized_rows,
        manifest=sanitized.manifest,
        splits=splits,
        content_hash=artifact_content_hash,
        source_format=request.source_format,
        normalized=request.normalize,
    )


def persist_sanitized_artifact(
    *,
    project_dir: Path,
    response: SanitizeDatasetResponse,
) -> Path:
    """Write the sanitized artifact + manifest to the project's datasets directory.

    The Modal upload pipeline only sends `sanitized.jsonl`; raw datasets stay
    on the host. Writes are atomic (tmp file + os.replace) so a partial write
    can never be observed by the orchestrator's `_require_sanitized_artifact`
    gate or by the Modal upload path.
    """
    datasets_dir = project_dir / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = datasets_dir / PERSISTED_DATASET_FILENAME
    manifest_path = datasets_dir / PERSISTED_MANIFEST_FILENAME

    tmp_artifact = artifact_path.with_suffix(".jsonl.tmp")
    with tmp_artifact.open("w", encoding="utf-8") as handle:
        for row in response.sanitized_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp_artifact, artifact_path)

    manifest_payload = {
        "content_hash": response.content_hash,
        "total_rows": response.total_rows,
        "source_format": response.source_format,
        "normalized": response.normalized,
        "redaction_counts": response.manifest.per_pattern,
        "total_redactions": response.manifest.total_redactions,
        "split_counts": response.splits.counts,
    }
    tmp_manifest = manifest_path.with_suffix(".json.tmp")
    tmp_manifest.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
    os.replace(tmp_manifest, manifest_path)

    return artifact_path


def get_sanitize_status(*, project_dir: Path) -> SanitizeArtifactStatus:
    """Report whether a persisted sanitized artifact exists for the project.

    `sanitized_at` is derived from the manifest file's mtime because the
    manifest payload itself does not carry a timestamp. Both the artifact and
    the manifest are written atomically via os.replace, so the manifest's
    mtime is a reliable proxy for when sanitization completed.
    """
    datasets_dir = project_dir / "datasets"
    artifact_path = datasets_dir / PERSISTED_DATASET_FILENAME
    manifest_path = datasets_dir / PERSISTED_MANIFEST_FILENAME
    if not artifact_path.is_file() or not manifest_path.is_file():
        return SanitizeArtifactStatus(exists=False, content_hash=None, sanitized_at=None)
    try:
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return SanitizeArtifactStatus(exists=False, content_hash=None, sanitized_at=None)
    content_hash = manifest_payload.get("content_hash")
    content_hash = content_hash if isinstance(content_hash, str) else None
    sanitized_at = datetime.fromtimestamp(manifest_path.stat().st_mtime, tz=UTC).isoformat()
    return SanitizeArtifactStatus(
        exists=True, content_hash=content_hash, sanitized_at=sanitized_at
    )
