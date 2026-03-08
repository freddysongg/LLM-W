from __future__ import annotations

from pydantic import BaseModel


class SuggestionResponse(BaseModel):
    id: str
    project_id: str
    source_run_id: str | None
    provider: str
    config_diff: str
    rationale: str
    evidence_json: str | None
    expected_effect: str | None
    tradeoffs: str | None
    confidence: float | None
    risk_level: str | None
    status: str
    applied_config_version_id: str | None
    created_at: str
    resolved_at: str | None

    model_config = {"from_attributes": True}


class SuggestionListResponse(BaseModel):
    items: list[SuggestionResponse]
    total: int


class SuggestionGenerateRequest(BaseModel):
    source_run_id: str | None = None
    notes: str | None = None


class SuggestionResolve(BaseModel):
    action: str
