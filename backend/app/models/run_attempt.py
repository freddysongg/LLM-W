from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.run import Run


class RunAttempt(Base):
    __tablename__ = "run_attempts"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "attempt_index",
            name="uq_run_attempts_run_id_attempt_index",
        ),
        Index("idx_run_attempts_run_id", "run_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    gpu_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    device: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str] = mapped_column(Text, nullable=False)
    ended_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_estimate_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped[Run] = relationship("Run", back_populates="attempts")
