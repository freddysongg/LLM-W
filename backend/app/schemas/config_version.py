from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ConfigVersionCreate(BaseModel):
    yaml_content: str
    source_tag: Literal["user", "ai_suggestion", "system"]
    source_detail: str | None = None


class ConfigVersionResponse(BaseModel):
    id: str
    project_id: str
    version_number: int
    yaml_hash: str
    diff_from_prev: str | None
    source_tag: str
    source_detail: str | None
    created_at: str

    model_config = {"from_attributes": True}


class ConfigDiffResponse(BaseModel):
    version_a_id: str
    version_b_id: str
    diff: dict[str, Any]
