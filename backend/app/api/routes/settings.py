from __future__ import annotations

from fastapi import APIRouter

from app.schemas.settings import AITestResponse, ModalTestResponse, SettingsResponse, SettingsUpdate
from app.services import settings_service

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    return settings_service.get_settings()


@router.patch("", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdate) -> SettingsResponse:
    return settings_service.update_settings(payload=payload)


@router.post("/ai/test", response_model=AITestResponse)
async def test_ai_connection() -> AITestResponse:
    return await settings_service.test_ai_connection()


@router.post("/modal/test", response_model=ModalTestResponse)
async def test_modal_connection() -> ModalTestResponse:
    return await settings_service.test_modal_connection()
