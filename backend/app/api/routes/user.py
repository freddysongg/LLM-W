from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.user import CurrentUserResponse

router = APIRouter(tags=["user"])


@router.get("/api/v1/me", response_model=CurrentUserResponse)
async def get_current_user() -> CurrentUserResponse:
    return CurrentUserResponse(
        id=settings.local_user_id,
        name=settings.local_user_name,
        email=settings.local_user_email,
    )
