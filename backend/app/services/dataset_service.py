from __future__ import annotations

import csv
import hashlib
import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConfigVersionNotFoundError,
    DatasetNotResolvedError,
    DatasetResolveError,
)
from app.schemas.config_version import ConfigVersionCreate
from app.schemas.dataset import (
    DatasetProfile,
    DatasetResolveRequest,
    DatasetSample,
    DatasetSamplesResponse,
    PreviewTransformRequest,
    PreviewTransformResponse,
    QualityWarning,
    SplitCounts,
    TokenStats,
)
from app.services import config_service, project_service

# In-memory state keyed by project_id
_profiles: dict[str, DatasetProfile] = {}
_samples: dict[str, list[dict[str, Any]]] = {}


def _approximate_token_count(row: dict[str, Any]) -> int:
    """Approximate token count as character count / 4."""
    return max(1, len(json.dumps(row)) // 4)


def _compute_row_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()


def _detect_format(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "default"
    sample = rows[0]
    if "conversations" in sample:
        return "sharegpt"
    if "messages" in sample:
        return "openai"
    if "instruction" in sample and "output" in sample:
        return "alpaca"
    return "default"


def _collect_fields(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    for row in rows[:100]:  # Sample first 100 for field detection
        seen.update(row.keys())
    return sorted(seen)


def _compute_quality_warnings(
    *, rows: list[dict[str, Any]], detected_format: str
) -> tuple[list[QualityWarning], int, int]:
    warnings: list[QualityWarning] = []
    hash_counts: dict[str, int] = {}
    malformed = 0

    for row in rows:
        row_hash = _compute_row_hash(row)
        hash_counts[row_hash] = hash_counts.get(row_hash, 0) + 1
        # A row is malformed if it has no content (all empty values)
        if all(v in (None, "", [], {}) for v in row.values()):
            malformed += 1

    duplicate_count = sum(count - 1 for count in hash_counts.values() if count > 1)

    if duplicate_count > 0:
        warnings.append(
            QualityWarning(
                code="DUPLICATES_DETECTED",
                message=f"{duplicate_count} duplicate rows detected.",
                count=duplicate_count,
            )
        )
    if malformed > 0:
        warnings.append(
            QualityWarning(
                code="MALFORMED_ROWS",
                message=f"{malformed} rows have all-empty values.",
                count=malformed,
            )
        )

    # Format-specific validation
    if detected_format == "sharegpt":
        missing_conversations = sum(1 for r in rows if "conversations" not in r)
        if missing_conversations > 0:
            warnings.append(
                QualityWarning(
                    code="MISSING_CONVERSATIONS_FIELD",
                    message=(
                        f"{missing_conversations} rows missing 'conversations' field "
                        "for sharegpt format."
                    ),
                    count=missing_conversations,
                )
            )
    elif detected_format == "openai":
        missing_messages = sum(1 for r in rows if "messages" not in r)
        if missing_messages > 0:
            warnings.append(
                QualityWarning(
                    code="MISSING_MESSAGES_FIELD",
                    message=f"{missing_messages} rows missing 'messages' field for openai format.",
                    count=missing_messages,
                )
            )

    return warnings, duplicate_count, malformed


def _compute_token_stats(rows: list[dict[str, Any]]) -> TokenStats | None:
    if not rows:
        return None
    counts = sorted(_approximate_token_count(row) for row in rows)
    n = len(counts)
    return TokenStats(
        min=counts[0],
        max=counts[-1],
        mean=round(statistics.mean(counts), 2),
        median=round(statistics.median(counts), 2),
        p95=round(counts[int(n * 0.95)], 2),
        p99=round(counts[int(n * 0.99)], 2),
    )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(dict(row))
    return rows


def _load_huggingface(
    *,
    dataset_id: str,
    subset: str | None,
    train_split: str,
    eval_split: str | None,
) -> tuple[list[dict[str, Any]], SplitCounts]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise DatasetResolveError(
            "datasets is not installed. Install the training extras: "
            "pip install 'llm-workbench-backend[training]'"
        ) from exc

    splits_to_load = [s for s in [train_split, eval_split] if s]
    all_rows: list[dict[str, Any]] = []
    split_counts = SplitCounts()

    for split_name in splits_to_load:
        try:
            ds = load_dataset(dataset_id, subset, split=split_name)
            split_rows = [dict(row) for row in ds]
            count = len(split_rows)
            if split_name == train_split:
                split_counts = SplitCounts(
                    train=count,
                    validation=split_counts.validation,
                    test=split_counts.test,
                )
                all_rows = split_rows
            elif split_name == eval_split:
                split_counts = SplitCounts(
                    train=split_counts.train,
                    validation=count,
                    test=split_counts.test,
                )
        except Exception:
            # Split may not exist; skip it
            pass

    return all_rows, split_counts


def _resolve_local(
    *,
    dataset_id: str,
    source: Literal["local_jsonl", "local_csv", "custom"],
) -> list[dict[str, Any]]:
    path = Path(dataset_id)
    if not path.exists():
        raise DatasetResolveError(f"Local dataset file not found: {dataset_id}")

    if source == "local_jsonl" or path.suffix == ".jsonl":
        return _load_jsonl(path)
    if source == "local_csv" or path.suffix == ".csv":
        return _load_csv(path)
    # custom: attempt JSONL first, then CSV
    try:
        return _load_jsonl(path)
    except json.JSONDecodeError:
        return _load_csv(path)


async def _write_resolved_dataset_to_config(
    *,
    session: AsyncSession,
    project_id: str,
    profile: DatasetProfile,
    request: DatasetResolveRequest,
) -> None:
    """Persist resolved dataset_id and source into the active config YAML version."""
    active = await config_service.get_active_config_version(session=session, project_id=project_id)
    raw_yaml = await config_service.get_config_yaml(
        session=session, project_id=project_id, version_id=active.id
    )
    parsed: dict[str, Any] = yaml.safe_load(raw_yaml) or {}
    dataset_section: dict[str, Any] = parsed.setdefault("dataset", {})
    dataset_section["dataset_id"] = profile.dataset_id
    dataset_section["source"] = profile.source
    dataset_section["train_split"] = request.train_split
    if request.eval_split is not None:
        dataset_section["eval_split"] = request.eval_split
    else:
        dataset_section.pop("eval_split", None)
    if request.max_samples is not None:
        dataset_section["max_samples"] = request.max_samples
    else:
        dataset_section.pop("max_samples", None)
    dataset_section.pop("filter_expression", None)
    updated_yaml = yaml.dump(parsed, default_flow_style=False, allow_unicode=True, sort_keys=False)
    new_version = await config_service.create_config_version(
        session=session,
        project_id=project_id,
        payload=ConfigVersionCreate(
            yaml_content=updated_yaml,
            source_tag="system",
            source_detail=f"dataset resolved: {profile.dataset_id}",
        ),
    )
    await project_service.set_active_config_version(
        session=session, project_id=project_id, config_version_id=new_version.id
    )


async def resolve_dataset(
    *, project_id: str, request: DatasetResolveRequest, session: AsyncSession
) -> DatasetProfile:
    rows: list[dict[str, Any]]
    split_counts: SplitCounts

    if request.source == "huggingface":
        rows, split_counts = _load_huggingface(
            dataset_id=request.dataset_id,
            subset=request.subset,
            train_split=request.train_split,
            eval_split=request.eval_split,
        )
    else:
        rows = _resolve_local(dataset_id=request.dataset_id, source=request.source)
        split_counts = SplitCounts(train=len(rows))

    if request.max_samples is not None and len(rows) > request.max_samples:
        rows = rows[: request.max_samples]

    detected_format = request.format if request.format != "default" else _detect_format(rows)
    detected_fields = _collect_fields(rows)
    token_stats = _compute_token_stats(rows)
    quality_warnings, duplicate_count, malformed_count = _compute_quality_warnings(
        rows=rows, detected_format=detected_format
    )

    profile = DatasetProfile(
        dataset_id=request.dataset_id,
        source=request.source,
        format=detected_format,
        total_rows=len(rows),
        split_counts=split_counts,
        detected_fields=detected_fields,
        token_stats=token_stats,
        quality_warnings=quality_warnings,
        duplicate_count=duplicate_count,
        malformed_count=malformed_count,
        resolved_at=datetime.now(UTC).isoformat(),
    )

    _profiles[project_id] = profile
    _samples[project_id] = rows
    try:
        await _write_resolved_dataset_to_config(
            session=session, project_id=project_id, profile=profile, request=request
        )
    except ConfigVersionNotFoundError:
        _profiles.pop(project_id, None)
        _samples.pop(project_id, None)
        raise
    return profile


def get_dataset_profile(*, project_id: str) -> DatasetProfile:
    profile = _profiles.get(project_id)
    if profile is None:
        raise DatasetNotResolvedError(project_id)
    return profile


def get_dataset_samples(
    *, project_id: str, limit: int = 20, offset: int = 0
) -> DatasetSamplesResponse:
    if project_id not in _profiles:
        raise DatasetNotResolvedError(project_id)
    rows = _samples.get(project_id, [])
    total = len(rows)
    page = rows[offset : offset + limit]
    return DatasetSamplesResponse(
        total=total,
        offset=offset,
        limit=limit,
        samples=[DatasetSample(index=offset + i, row=row) for i, row in enumerate(page)],
    )


def get_token_stats(*, project_id: str) -> TokenStats:
    profile = _profiles.get(project_id)
    if profile is None:
        raise DatasetNotResolvedError(project_id)
    if profile.token_stats is None:
        rows = _samples.get(project_id, [])
        computed = _compute_token_stats(rows)
        if computed is None:
            raise DatasetResolveError("No rows available to compute token statistics.")
        return computed
    return profile.token_stats


def _apply_format_mapping(
    row: dict[str, Any], format_mapping: dict[str, str] | None
) -> dict[str, Any]:
    if not format_mapping:
        return row
    mapped = {}
    for key, value in row.items():
        mapped_key = format_mapping.get(key, key)
        mapped[mapped_key] = value
    return mapped


def _transform_row(
    *,
    row: dict[str, Any],
    fmt: str,
    format_mapping: dict[str, str] | None,
) -> dict[str, Any]:
    row = _apply_format_mapping(row, format_mapping)
    if fmt == "sharegpt":
        conversations = row.get("conversations", [])
        return {"conversations": conversations}
    if fmt == "openai":
        messages = row.get("messages", [])
        return {"messages": messages}
    if fmt == "alpaca":
        return {
            "instruction": row.get("instruction", ""),
            "input": row.get("input", ""),
            "output": row.get("output", ""),
        }
    return row


def preview_transform(
    *, project_id: str, request: PreviewTransformRequest
) -> PreviewTransformResponse:
    if project_id not in _profiles:
        raise DatasetNotResolvedError(project_id)
    rows = _samples.get(project_id, [])
    count = min(request.sample_count, len(rows))
    transformed = [
        _transform_row(
            row=rows[i],
            fmt=request.format,
            format_mapping=request.format_mapping,
        )
        for i in range(count)
    ]
    return PreviewTransformResponse(
        samples=transformed,
        format_applied=request.format,
        truncated=len(rows) > request.sample_count,
    )
