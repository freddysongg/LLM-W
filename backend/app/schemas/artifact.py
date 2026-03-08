from __future__ import annotations

from pydantic import BaseModel


class ArtifactResponse(BaseModel):
    id: str
    run_id: str
    project_id: str
    artifact_type: str
    file_path: str
    file_size_bytes: int | None
    metadata_json: str | None
    is_retained: int
    created_at: str

    model_config = {"from_attributes": True}


class ArtifactListResponse(BaseModel):
    items: list[ArtifactResponse]
    total: int


class ArtifactCleanupResponse(BaseModel):
    deleted_count: int
    freed_bytes: int
    retained_count: int
