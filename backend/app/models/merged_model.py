from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.run import Run


class MergedModel(Base):
    __tablename__ = "merged_models"
    __table_args__ = (
        Index("idx_merged_models_project", "project_id"),
        Index("idx_merged_models_source_run", "source_run_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("projects.id"), nullable=False
    )
    base_model_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_run_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("runs.id"), nullable=True
    )
    adapter_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    project: Mapped[Project] = relationship("Project")
    source_run: Mapped[Run | None] = relationship(
        "Run", foreign_keys=[source_run_id]
    )
