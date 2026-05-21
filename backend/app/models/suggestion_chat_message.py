from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SuggestionChatMessage(Base):
    __tablename__ = "suggestion_chat_messages"
    __table_args__ = (
        Index("idx_suggestion_chat_messages_suggestion", "suggestion_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    suggestion_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_suggestions.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
