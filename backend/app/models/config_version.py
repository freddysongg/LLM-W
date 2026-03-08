from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.project import Project


class ConfigVersion(Base):
    __tablename__ = "config_versions"
    __table_args__ = (UniqueConstraint("project_id", "version_number"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("projects.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    yaml_blob: Mapped[str] = mapped_column(Text, nullable=False)
    yaml_hash: Mapped[str] = mapped_column(Text, nullable=False)
    diff_from_prev: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_tag: Mapped[str] = mapped_column(Text, nullable=False)
    source_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    project: Mapped[Project] = relationship(
        "Project",
        back_populates="config_versions",
        foreign_keys=[project_id],
    )
