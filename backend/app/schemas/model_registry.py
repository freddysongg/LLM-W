from __future__ import annotations

from pydantic import BaseModel


class ModelRegistryEntryResponse(BaseModel):
    name: str
    params: str
    context: str
    license: str
    source: str
    is_pinned: bool

    model_config = {"from_attributes": True}


class ModelRegistryResponse(BaseModel):
    entries: list[ModelRegistryEntryResponse]
