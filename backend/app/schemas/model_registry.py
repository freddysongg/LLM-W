from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

RegisterModelSource = Literal["hf", "local", "s3"]
RegisterModelDtype = Literal["bfloat16", "float16", "float32", "int8", "int4"]


class ModelRegistryEntryResponse(BaseModel):
    name: str
    source: str
    is_pinned: bool
    params: str | None = None
    context: str | None = None
    license: str | None = None
    path: str | None = None
    dtype: str | None = None

    model_config = {"from_attributes": True}


class ModelRegistryResponse(BaseModel):
    entries: list[ModelRegistryEntryResponse]


class RegisterModelEntryRequest(BaseModel):
    name: str
    source: RegisterModelSource
    path: str
    dtype: RegisterModelDtype
    is_pinned: bool
