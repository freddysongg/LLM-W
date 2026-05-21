from __future__ import annotations

from pydantic import BaseModel


class ModalGpuOptionResponse(BaseModel):
    gpu_type: str
    label: str
    vram_gb: int
    rate_usd_hr: float

    model_config = {"from_attributes": True}


class ModalGpuCatalogResponse(BaseModel):
    options: list[ModalGpuOptionResponse]
