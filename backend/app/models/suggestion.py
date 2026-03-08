from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.config_version import ConfigVersion
    from app.models.project import Project
    from app.models.run import Run


class AISuggestion(Base):
    __tablename__ = "ai_suggestions"
    __table_args__ = (
        Index("idx_suggestions_project", "project_id"),
        Index("idx_suggestions_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("projects.id"), nullable=False)
    source_run_id: Mapped[str | None] = mapped_column(Text, ForeignKey("runs.id"), nullable=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    config_diff: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_effect: Mapped[str | None] = mapped_column(Text, nullable=True)
    tradeoffs: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    applied_config_version_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("config_versions.id"), nullable=True
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="ai_suggestions")
    source_run: Mapped[Run | None] = relationship(
        "Run", back_populates="ai_suggestions", foreign_keys=[source_run_id]
    )
    applied_config_version: Mapped[ConfigVersion | None] = relationship(
        "ConfigVersion", foreign_keys=[applied_config_version_id]
    )
