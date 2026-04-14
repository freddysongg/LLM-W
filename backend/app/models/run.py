from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, Integer, Text
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
    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_stage: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checkpoint_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    heartbeat_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_type: Mapped[str] = mapped_column(Text, nullable=False, default="training")
    device: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_per_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_to_first_checkpoint_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    wall_clock_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    peak_memory_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    heldout_perplexity: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    judge_pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    eval_split_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_unavailable_reasons: Mapped[str | None] = mapped_column(Text, nullable=True)
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
