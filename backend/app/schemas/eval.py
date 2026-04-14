from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class EvaluationCase(BaseModel):
    """Input payload passed to a judge call."""

    prompt: str
    output: str
    reference: str | None = None
    retrieved_context: str | None = None
    conversation_history: list[dict[str, str]] | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @field_validator("conversation_history")
    @classmethod
    def _validate_conversation_history(
        cls, history: list[dict[str, str]] | None
    ) -> list[dict[str, str]] | None:
        if history is None:
            return None
        for turn in history:
            if set(turn.keys()) != {"role", "content"}:
                raise ValueError(
                    "conversation_history entries must contain exactly 'role' and 'content' keys"
                )
        return history


class Score(BaseModel):
    """Output payload returned by a judge call.

    Field order is load-bearing: `reasoning` must precede `verdict` so that
    OpenAI Structured Outputs / `instructor` emit chain-of-thought reasoning
    before the verdict token (G-Eval / Critique Shadowing, R3 / R7).
    """

    reasoning: str = Field(..., min_length=1)
    verdict: Literal["pass", "fail"]
    per_criterion: dict[str, bool]
    cost_usd: float = Field(default=0.0, ge=0.0)
    latency_ms: int = Field(..., ge=0)
    judge_model: str = Field(..., min_length=1)
    rubric_version: str = Field(..., min_length=1)
    response_hash: str = Field(..., pattern=r"^[a-f0-9]{64}$")

    model_config = {"extra": "forbid"}

    @field_validator("reasoning")
    @classmethod
    def _reasoning_not_blank(cls, reasoning: str) -> str:
        if not reasoning.strip():
            raise ValueError("reasoning must not be empty or whitespace-only")
        return reasoning
