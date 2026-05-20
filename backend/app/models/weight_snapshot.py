from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, PrimaryKeyConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WeightSnapshot(Base):
    __tablename__ = "weight_snapshots"
    __table_args__ = (
        PrimaryKeyConstraint("run_id", "step", "layer_name"),
        Index("idx_weight_snapshots_run_layer_step", "run_id", "layer_name", "step"),
    )

    run_id: Mapped[str] = mapped_column(Text, ForeignKey("runs.id"), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    layer_name: Mapped[str] = mapped_column(Text, nullable=False)
    mean: Mapped[float] = mapped_column(Float, nullable=False)
    std: Mapped[float] = mapped_column(Float, nullable=False)
    norm: Mapped[float] = mapped_column(Float, nullable=False)
    min_val: Mapped[float] = mapped_column(Float, nullable=False)
    max_val: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
