from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class EvalRunCreate(BaseModel):
    """REST body for POST /api/v1/eval/runs."""

    project_id: str = Field(min_length=1)
    training_run_id: str | None = None
    rubric_version_ids: list[str] = Field(min_length=1)
    max_cost_usd: float | None = Field(default=None, gt=0.0)

    model_config = ConfigDict(extra="forbid")


class EvalRunSummary(BaseModel):
    """Row-level eval_run projection used across list and detail responses."""

    id: str
    training_run_id: str | None
    status: str
    started_at: str
    completed_at: str | None
    pass_rate: float | None
    total_cost_usd: float
    max_cost_usd: float | None

    model_config = ConfigDict(from_attributes=True)


class EvalRunListResponse(BaseModel):
    items: list[EvalRunSummary]
    total: int
    limit: int
    offset: int


class EvaluationCasePayload(BaseModel):
    """Structured representation of an eval_case.case_input blob."""

    prompt: str
    output: str
    reference: str | None = None
    retrieved_context: str | None = None
    conversation_history: list[dict[str, str]] | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class EvalCaseRow(BaseModel):
    """Response shape for an eval_cases row as consumed by the frontend."""

    id: str
    eval_run_id: str
    case_input: EvaluationCasePayload
    input_hash: str


class EvalCallRow(BaseModel):
    """Response shape for an eval_calls row as consumed by the frontend."""

    id: str
    eval_run_id: str
    case_id: str
    rubric_version_id: str
    judge_model: str
    tier: str
    verdict: str
    reasoning: str
    per_criterion: dict[str, bool] | None
    response_hash: str
    cost_usd: float
    latency_ms: int | None
    replayed_from_id: str | None
    created_at: str


class EvalRunDetailResponse(BaseModel):
    run: EvalRunSummary
    cases: list[EvalCaseRow]
    calls: list[EvalCallRow]


class EvalCallsPageResponse(BaseModel):
    items: list[EvalCallRow]
    total: int
    limit: int
    offset: int


class RubricVersionSummary(BaseModel):
    id: str
    rubric_id: str
    version_number: int
    content_hash: str
    calibration_status: str
    judge_model_pin: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class RubricSummary(BaseModel):
    id: str
    name: str
    description: str
    research_basis: str | None
    versions: list[RubricVersionSummary]
    created_at: str

    model_config = ConfigDict(from_attributes=True)
