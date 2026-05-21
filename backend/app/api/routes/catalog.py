from __future__ import annotations

from fastapi import APIRouter

from app.core.llm_catalog import LLM_MODEL_CATALOG
from app.core.modal_catalog import MODAL_GPU_CATALOG
from app.schemas.catalog import ModalGpuCatalogResponse, ModalGpuOptionResponse
from app.schemas.llm_catalog import LlmCatalogResponse, LlmModelOptionResponse
from app.schemas.model_registry import (
    ModelRegistryEntryResponse,
    ModelRegistryResponse,
    RegisterModelEntryRequest,
)
from app.services import model_registry_service

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/modal-gpus", response_model=ModalGpuCatalogResponse)
async def list_modal_gpus() -> ModalGpuCatalogResponse:
    return ModalGpuCatalogResponse(
        options=[ModalGpuOptionResponse.model_validate(option) for option in MODAL_GPU_CATALOG]
    )


@router.get("/llm-models", response_model=LlmCatalogResponse)
async def list_llm_models() -> LlmCatalogResponse:
    return LlmCatalogResponse(
        options=[LlmModelOptionResponse.model_validate(option) for option in LLM_MODEL_CATALOG]
    )


@router.get("/model-registry", response_model=ModelRegistryResponse)
async def list_model_registry() -> ModelRegistryResponse:
    return ModelRegistryResponse(entries=model_registry_service.list_entries())


@router.post("/model-registry", response_model=ModelRegistryEntryResponse, status_code=201)
async def register_model_entry(
    payload: RegisterModelEntryRequest,
) -> ModelRegistryEntryResponse:
    return model_registry_service.register_entry(request=payload)
