from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.project import Project


class ModelProfile(Base):
    __tablename__ = "model_profiles"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("projects.id"), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    family: Mapped[str] = mapped_column(Text, nullable=False)
    architecture_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameter_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trainable_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokenizer_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    vocab_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_position_embeddings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hidden_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_layers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_attention_heads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capabilities_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_estimate_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    project: Mapped[Project] = relationship("Project", back_populates="model_profiles")
