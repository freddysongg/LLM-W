from __future__ import annotations

from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("idx_notifications_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    subtitle: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[str | None] = mapped_column(Text, nullable=True)
