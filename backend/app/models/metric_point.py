from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Real, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.run import Run


class MetricPoint(Base):
    __tablename__ = "metric_points"
    __table_args__ = (
        Index("idx_metrics_run_step", "run_id", "step"),
        Index("idx_metrics_run_name", "run_id", "metric_name"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text, ForeignKey("runs.id"), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    epoch: Mapped[float | None] = mapped_column(Real, nullable=True)
    metric_name: Mapped[str] = mapped_column(Text, nullable=False)
    metric_value: Mapped[float] = mapped_column(Real, nullable=False)
    stage_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped[Run] = relationship("Run", back_populates="metric_points")
