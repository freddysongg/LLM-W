from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Real, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.artifact import Artifact
    from app.models.config_version import ConfigVersion
    from app.models.metric_point import MetricPoint
    from app.models.project import Project
    from app.models.run_stage import RunStage
    from app.models.suggestion import AISuggestion


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        Index("idx_runs_project", "project_id"),
        Index("idx_runs_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("projects.id"), nullable=False)
    config_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("config_versions.id"), nullable=False
    )
    parent_run_id: Mapped[str | None] = mapped_column(Text, ForeignKey("runs.id"), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    current_stage: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_pct: Mapped[float] = mapped_column(Real, nullable=False, default=0.0)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_stage: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checkpoint_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    heartbeat_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    project: Mapped[Project] = relationship("Project", back_populates="runs")
    config_version: Mapped[ConfigVersion] = relationship(
        "ConfigVersion", foreign_keys=[config_version_id]
    )
    stages: Mapped[list[RunStage]] = relationship(
        "RunStage", back_populates="run", cascade="all, delete-orphan"
    )
    metric_points: Mapped[list[MetricPoint]] = relationship(
        "MetricPoint", back_populates="run", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list[Artifact]] = relationship(
        "Artifact", back_populates="run", cascade="all, delete-orphan"
    )
    ai_suggestions: Mapped[list[AISuggestion]] = relationship(
        "AISuggestion", back_populates="source_run", foreign_keys="AISuggestion.source_run_id"
    )
