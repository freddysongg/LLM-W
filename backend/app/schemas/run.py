from __future__ import annotations

from pydantic import BaseModel


class RunCreate(BaseModel):
    config_version_id: str
    parent_run_id: str | None = None


class RunResponse(BaseModel):
    id: str
    project_id: str
    config_version_id: str
    parent_run_id: str | None
    status: str
    current_stage: str | None
    current_step: int
    total_steps: int | None
    progress_pct: float
    started_at: str | None
    completed_at: str | None
    failure_reason: str | None
    failure_stage: str | None
    last_checkpoint_path: str | None
    pid: int | None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class RunStageResponse(BaseModel):
    id: str
    run_id: str
    stage_name: str
    stage_order: int
    status: str
    started_at: str | None
    completed_at: str | None
    duration_ms: int | None
    warnings_json: str | None
    output_summary: str | None
    created_at: str

    model_config = {"from_attributes": True}
