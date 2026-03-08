from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.run import Run


class ActivationSnapshot(Base):
    __tablename__ = "activation_snapshots"
    __table_args__ = (
        Index("idx_activations_run", "run_id"),
        Index("idx_activations_layer", "layer_name"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text, ForeignKey("runs.id"), nullable=False)
    checkpoint_step: Mapped[int] = mapped_column(Integer, nullable=False)
    layer_name: Mapped[str] = mapped_column(Text, nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False)
    full_tensor_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_input_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped[Run] = relationship("Run")
