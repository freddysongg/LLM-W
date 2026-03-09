from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class DatasetResolveRequest(BaseModel):
    source: Literal["huggingface", "local_jsonl", "local_csv", "custom"]
    dataset_id: str
    subset: str | None = None
    train_split: str = "train"
    eval_split: str | None = "validation"
    max_samples: int | None = None
    format: Literal["default", "sharegpt", "openai", "alpaca", "custom"] = "default"
    format_mapping: dict[str, str] | None = None
    train_ratio: float | None = None
    val_ratio: float | None = None
    test_ratio: float | None = None


class SplitCounts(BaseModel):
    train: int | None = None
    validation: int | None = None
    test: int | None = None


class TokenStats(BaseModel):
    min: int
    max: int
    mean: float
    median: float
    p95: float
    p99: float


class QualityWarning(BaseModel):
    code: str
    message: str
    count: int | None = None


class DatasetProfile(BaseModel):
    dataset_id: str
    source: Literal["huggingface", "local_jsonl", "local_csv", "custom"]
    format: str
    total_rows: int
    split_counts: SplitCounts
    detected_fields: list[str]
    token_stats: TokenStats | None
    quality_warnings: list[QualityWarning]
    duplicate_count: int
    malformed_count: int
    resolved_at: str


class DatasetSample(BaseModel):
    index: int
    row: dict[str, Any]


class DatasetSamplesResponse(BaseModel):
    total: int
    offset: int
    limit: int
    samples: list[DatasetSample]


class PreviewTransformRequest(BaseModel):
    format: Literal["default", "sharegpt", "openai", "alpaca", "custom"]
    format_mapping: dict[str, str] | None = None
    sample_count: int = 5


class PreviewTransformResponse(BaseModel):
    samples: list[dict[str, Any]]
    format_applied: str
    truncated: bool
