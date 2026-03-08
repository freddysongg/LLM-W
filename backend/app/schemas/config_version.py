from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, field_validator


class ConfigVersionCreate(BaseModel):
    yaml_content: str
    source_tag: Literal["user", "ai_suggestion", "system"]
    source_detail: str | None = None


class ConfigVersionResponse(BaseModel):
    id: str
    project_id: str
    version_number: int
    yaml_hash: str
    diff_from_prev: dict[str, Any] | None
    source_tag: str
    source_detail: str | None
    created_at: str

    model_config = {"from_attributes": True}

    @field_validator("diff_from_prev", mode="before")
    @classmethod
    def parse_diff_json(cls, v: str | dict | None) -> dict[str, Any] | None:
        if v is None:
            return None
        if isinstance(v, str):
            return json.loads(v)  # type: ignore[no-any-return]
        return v


class ConfigVersionListResponse(BaseModel):
    items: list[ConfigVersionResponse]
    total: int
    limit: int
    offset: int


class ConfigDiffResponse(BaseModel):
    version_a_id: str
    version_b_id: str
    diff: dict[str, Any]


class ConfigValidationResponse(BaseModel):
    is_valid: bool
    errors: list[str]
