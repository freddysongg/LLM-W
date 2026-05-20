from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotificationNotFoundError
from app.models.notification import Notification


async def list_notifications(*, session: AsyncSession) -> list[Notification]:
    result = await session.execute(
        select(Notification).order_by(Notification.created_at.desc())
    )
    return list(result.scalars().all())


async def mark_read(*, session: AsyncSession, notification_id: str) -> Notification:
    notification = await session.get(Notification, notification_id)
    if notification is None:
        raise NotificationNotFoundError(notification_id)
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC).isoformat()
        await session.commit()
    return notification
