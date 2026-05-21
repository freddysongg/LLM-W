from __future__ import annotations

from pydantic import BaseModel


class MergedModelResponse(BaseModel):
    id: str
    project_id: str
    base_model_id: str
    source_run_id: str | None
    adapter_step: int | None
    file_path: str
    file_size_bytes: int
    created_at: str

    model_config = {"from_attributes": True}


class MergedModelListResponse(BaseModel):
    items: list[MergedModelResponse]
    total: int


class MergeRunRequest(BaseModel):
    source_run_id: str
