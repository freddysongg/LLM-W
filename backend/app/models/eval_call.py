from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.eval_case import EvalCase
    from app.models.eval_run import EvalRun
    from app.models.rubric_version import RubricVersion


class EvalCall(Base):
    __tablename__ = "eval_calls"
    __table_args__ = (
        Index("idx_eval_calls_eval_run", "eval_run_id"),
        Index("idx_eval_calls_case", "case_id"),
        Index("idx_eval_calls_rubric_version", "rubric_version_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    eval_run_id: Mapped[str] = mapped_column(Text, ForeignKey("eval_runs.id"), nullable=False)
    case_id: Mapped[str] = mapped_column(Text, ForeignKey("eval_cases.id"), nullable=False)
    rubric_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("rubric_versions.id"), nullable=False
    )
    judge_model: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    per_criterion: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_hash: Mapped[str] = mapped_column(Text, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    replayed_from_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("eval_calls.id"), nullable=True
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    eval_run: Mapped[EvalRun] = relationship("EvalRun", back_populates="calls")
    case: Mapped[EvalCase] = relationship("EvalCase", back_populates="calls")
    rubric_version: Mapped[RubricVersion] = relationship(
        "RubricVersion", foreign_keys=[rubric_version_id]
    )
    replayed_from: Mapped[EvalCall | None] = relationship(
        "EvalCall", remote_side=[id], foreign_keys=[replayed_from_id]
    )
