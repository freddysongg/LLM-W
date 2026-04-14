from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.eval import EvaluationCase

_LATEST_ALIAS_MARKER = "-latest"
_RESEARCH_BASIS_PATTERN = re.compile(r"^R\d+$")
_MIN_FEW_SHOT_EXAMPLES = 5


def _reject_latest_alias(model_pin: str) -> str:
    if _LATEST_ALIAS_MARKER in model_pin.lower():
        raise ValueError(
            "judge_model_pin must be a pinned SHA or dated version; '-latest' aliases are forbidden"
        )
    return model_pin


class Criterion(BaseModel):
    """Atomic binary check contributing additive points to a rubric (R11)."""

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    points: int = Field(ge=0, le=10)

    model_config = {"extra": "forbid"}


class FewShotExample(BaseModel):
    """Calibration example demonstrating a rubric verdict with reasoning."""

    input: EvaluationCase
    verdict: Literal["pass", "fail"]
    reasoning: str = Field(min_length=1)

    model_config = {"extra": "forbid"}


class ChainPollConfig(BaseModel):
    """Configuration for N-call majority voting (ChainPoll, default N=3)."""

    n: int = Field(ge=2, le=10)
    model: str = Field(min_length=1)
    temperature: float = Field(ge=0.0, le=1.0)

    model_config = {"extra": "forbid"}

    @field_validator("model")
    @classmethod
    def _reject_latest_in_model(cls, model_pin: str) -> str:
        return _reject_latest_alias(model_pin)


class Rubric(BaseModel):
    """Top-level rubric definition loaded from YAML."""

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    scale: Literal["binary"]
    criteria: list[Criterion] = Field(min_length=1)
    few_shot_examples: list[FewShotExample]
    judge_model_pin: str = Field(min_length=1)
    research_basis: list[str] = Field(min_length=1)
    chainpoll: ChainPollConfig | None = None

    model_config = {"extra": "forbid"}

    @field_validator("few_shot_examples")
    @classmethod
    def _require_minimum_mixed_examples(
        cls, examples: list[FewShotExample]
    ) -> list[FewShotExample]:
        if len(examples) < _MIN_FEW_SHOT_EXAMPLES:
            raise ValueError(
                f"rubric requires ≥{_MIN_FEW_SHOT_EXAMPLES} few-shot examples, got {len(examples)}"
            )
        has_pass = any(example.verdict == "pass" for example in examples)
        has_fail = any(example.verdict == "fail" for example in examples)
        if not has_pass:
            raise ValueError("few-shot examples must include at least one 'pass' instance")
        if not has_fail:
            raise ValueError("few-shot examples must include at least one 'fail' instance")
        return examples

    @field_validator("judge_model_pin")
    @classmethod
    def _reject_latest_in_judge_pin(cls, model_pin: str) -> str:
        return _reject_latest_alias(model_pin)

    @field_validator("research_basis")
    @classmethod
    def _validate_research_basis_ids(cls, basis: list[str]) -> list[str]:
        for entry in basis:
            if not _RESEARCH_BASIS_PATTERN.match(entry):
                raise ValueError(f"research_basis entries must match R<digits>, got {entry}")
        return basis
