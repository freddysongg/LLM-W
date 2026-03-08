from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.config_version import ConfigVersion
    from app.models.dataset_profile import DatasetProfile
    from app.models.decision_log import DecisionLog
    from app.models.model_profile import ModelProfile
    from app.models.run import Run
    from app.models.storage_record import StorageRecord
    from app.models.suggestion import AISuggestion


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    directory_path: Mapped[str] = mapped_column(Text, nullable=False)
    active_config_version_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("config_versions.id"), nullable=True
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    config_versions: Mapped[list[ConfigVersion]] = relationship(
        "ConfigVersion",
        back_populates="project",
        foreign_keys="ConfigVersion.project_id",
        cascade="all, delete-orphan",
    )
    runs: Mapped[list[Run]] = relationship(
        "Run", back_populates="project", cascade="all, delete-orphan"
    )
    model_profiles: Mapped[list[ModelProfile]] = relationship(
        "ModelProfile", back_populates="project", cascade="all, delete-orphan"
    )
    dataset_profiles: Mapped[list[DatasetProfile]] = relationship(
        "DatasetProfile", back_populates="project", cascade="all, delete-orphan"
    )
    ai_suggestions: Mapped[list[AISuggestion]] = relationship(
        "AISuggestion", back_populates="project", cascade="all, delete-orphan"
    )
    decision_logs: Mapped[list[DecisionLog]] = relationship(
        "DecisionLog", back_populates="project", cascade="all, delete-orphan"
    )
    storage_records: Mapped[list[StorageRecord]] = relationship(
        "StorageRecord", back_populates="project", cascade="all, delete-orphan"
    )
