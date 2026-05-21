from __future__ import annotations

from pydantic import BaseModel


class LlmModelOptionResponse(BaseModel):
    provider: str
    model_id: str
    label: str

    model_config = {"from_attributes": True}


class LlmCatalogResponse(BaseModel):
    options: list[LlmModelOptionResponse]
