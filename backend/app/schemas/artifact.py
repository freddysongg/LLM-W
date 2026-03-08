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
