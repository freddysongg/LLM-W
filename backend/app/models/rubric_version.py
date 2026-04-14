from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.rubric import Rubric


class RubricVersion(Base):
    __tablename__ = "rubric_versions"
    __table_args__ = (
        UniqueConstraint("rubric_id", "version_number"),
        Index("idx_rubric_versions_rubric", "rubric_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    rubric_id: Mapped[str] = mapped_column(Text, ForeignKey("rubrics.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    yaml_blob: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    diff_from_prev: Mapped[str | None] = mapped_column(Text, nullable=True)
    calibration_metrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    calibration_status: Mapped[str] = mapped_column(Text, nullable=False, default="uncalibrated")
    judge_model_pin: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    rubric: Mapped[Rubric] = relationship("Rubric", back_populates="versions")
