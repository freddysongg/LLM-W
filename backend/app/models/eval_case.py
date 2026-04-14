from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.eval_call import EvalCall
    from app.models.eval_run import EvalRun


class EvalCase(Base):
    __tablename__ = "eval_cases"
    __table_args__ = (Index("idx_eval_cases_eval_run", "eval_run_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    eval_run_id: Mapped[str] = mapped_column(Text, ForeignKey("eval_runs.id"), nullable=False)
    case_input: Mapped[str] = mapped_column(Text, nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)

    eval_run: Mapped[EvalRun] = relationship("EvalRun", back_populates="cases")
    calls: Mapped[list[EvalCall]] = relationship(
        "EvalCall", back_populates="case", cascade="all, delete-orphan"
    )
