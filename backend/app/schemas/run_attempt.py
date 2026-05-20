from __future__ import annotations

from pydantic import BaseModel


class RunAttemptResponse(BaseModel):
    id: str
    run_id: str
    attempt_index: int
    gpu_type: str | None
    device: str | None
    started_at: str
    ended_at: str | None
    exit_reason: str | None
    cost_estimate_usd: float | None
    created_at: str

    model_config = {"from_attributes": True}
