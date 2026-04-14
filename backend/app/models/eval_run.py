from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.eval_call import EvalCall
    from app.models.eval_case import EvalCase


class EvalRun(Base):
    __tablename__ = "eval_runs"
    __table_args__ = (Index("idx_eval_runs_training_run", "training_run_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    training_run_id: Mapped[str | None] = mapped_column(Text, ForeignKey("runs.id"), nullable=True)
    started_at: Mapped[str] = mapped_column(Text, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    cases: Mapped[list[EvalCase]] = relationship(
        "EvalCase", back_populates="eval_run", cascade="all, delete-orphan"
    )
    calls: Mapped[list[EvalCall]] = relationship(
        "EvalCall", back_populates="eval_run", cascade="all, delete-orphan"
    )
