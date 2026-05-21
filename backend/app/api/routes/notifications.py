from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import NotificationNotFoundError
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.services import notifications_service

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("", response_model=NotificationListResponse)
async def list_notifications(session: DbSession) -> NotificationListResponse:
    notifications = await notifications_service.list_notifications(session=session)
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(row) for row in notifications]
    )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: str, session: DbSession
) -> NotificationResponse:
    try:
        notification = await notifications_service.mark_read(
            session=session, notification_id=notification_id
        )
    except NotificationNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOTIFICATION_NOT_FOUND", "message": str(exc), "details": {}},
        ) from exc
    return NotificationResponse.model_validate(notification)
