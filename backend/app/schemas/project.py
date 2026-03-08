from __future__ import annotations

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    directory_path: str
    active_config_version_id: str | None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
