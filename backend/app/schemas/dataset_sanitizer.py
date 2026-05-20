from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

RedactionPatternName = Literal["email", "us_phone", "credit_card", "ssn", "ipv4"]
SourceFormat = Literal["openai", "sharegpt", "alpaca", "default"]
SplitName = Literal["train", "val", "test"]

_REDACTION_RATIO_TOLERANCE = 1e-6


class RedactionPattern(BaseModel):
    """A single named regex used to redact sensitive substrings from dataset rows."""

    name: RedactionPatternName
    regex: str = Field(min_length=1)
    replacement: str = Field(min_length=1)

    model_config = {"extra": "forbid"}


class SanitizationRules(BaseModel):
    """Bundle of redaction patterns applied to dataset rows in order."""

    patterns: list[RedactionPattern] = Field(min_length=1)

    model_config = {"extra": "forbid"}


class RedactionManifest(BaseModel):
    """Per-pattern redaction counts collected during a sanitization pass."""

    per_pattern: dict[str, int]
    total_redactions: int = Field(ge=0)

    model_config = {"extra": "forbid"}


class SanitizationResult(BaseModel):
    """Outcome of sanitizing a row batch, returned by the service to callers."""

    sanitized_rows: list[dict[str, object]]
    manifest: RedactionManifest
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    model_config = {"extra": "forbid"}


class SplitRatios(BaseModel):
    """Train/val/test fractions that must sum to 1.0 within tolerance."""

    train: float = Field(ge=0.0, le=1.0)
    val: float = Field(ge=0.0, le=1.0)
    test: float = Field(ge=0.0, le=1.0)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _ratios_must_sum_to_one(self) -> SplitRatios:
        total = self.train + self.val + self.test
        if abs(total - 1.0) > _REDACTION_RATIO_TOLERANCE:
            raise ValueError(
                f"split ratios must sum to 1.0 (got {total:.6f}: "
                f"train={self.train}, val={self.val}, test={self.test})"
            )
        return self


class SplitAssignment(BaseModel):
    """Mapping of row index -> assigned split name (deterministic per content)."""

    assignments: dict[int, SplitName]
    counts: dict[str, int]

    model_config = {"extra": "forbid"}


class SanitizeDatasetRequest(BaseModel):
    """REST body for POST /api/v1/projects/{project_id}/datasets/sanitize."""

    rules: SanitizationRules | None = None
    split_ratios: SplitRatios
    source_format: SourceFormat = "default"
    normalize: bool = True
    persist: bool = False

    model_config = {"extra": "forbid"}

    @field_validator("normalize")
    @classmethod
    def _normalize_implies_known_format(cls, normalize: bool) -> bool:
        return normalize


class SanitizeDatasetResponse(BaseModel):
    """Response from the sanitize endpoint with manifest, splits, and hash."""

    total_rows: int = Field(ge=0)
    sanitized_rows: list[dict[str, object]]
    manifest: RedactionManifest
    splits: SplitAssignment
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_format: SourceFormat
    normalized: bool

    model_config = {"extra": "forbid"}
