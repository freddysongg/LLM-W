from __future__ import annotations

from fastapi import APIRouter

from app.core.modal_catalog import MODAL_GPU_CATALOG
from app.schemas.catalog import ModalGpuCatalogResponse, ModalGpuOptionResponse

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/modal-gpus", response_model=ModalGpuCatalogResponse)
async def list_modal_gpus() -> ModalGpuCatalogResponse:
    return ModalGpuCatalogResponse(
        options=[ModalGpuOptionResponse.model_validate(option) for option in MODAL_GPU_CATALOG]
    )
