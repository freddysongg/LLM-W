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


class RunListResponse(BaseModel):
    items: list[RunResponse]
    total: int
    limit: int
    offset: int


class RunResumeResponse(BaseModel):
    new_run_id: str
    parent_run_id: str
    resume_from_checkpoint: str
    resume_from_step: int | None
    status: str


class RunLogLine(BaseModel):
    severity: str
    stage: str | None
    message: str
    source: str | None
    timestamp: str


class RunLogsResponse(BaseModel):
    lines: list[RunLogLine]
    total: int
    has_more: bool


class RunMetricSummary(BaseModel):
    final: float
    min: float
    trend: str


class RunArtifactCompareSummary(BaseModel):
    checkpoints: int
    total_size_mb: float


class RunCompareResponse(BaseModel):
    runs: list[str]
    config_diff: dict[str, object]
    metric_comparison: dict[str, dict[str, RunMetricSummary]]
    artifact_comparison: dict[str, RunArtifactCompareSummary]


class CheckpointResponse(BaseModel):
    id: str
    run_id: str
    project_id: str
    step: int | None
    file_path: str
    file_size_bytes: int | None
    metadata_json: str | None
    is_retained: bool
    created_at: str
