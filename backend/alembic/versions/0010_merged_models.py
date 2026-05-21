"""merged models table

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-20 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "merged_models",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Text(),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("base_model_id", sa.Text(), nullable=False),
        sa.Column(
            "source_run_id",
            sa.Text(),
            sa.ForeignKey("runs.id"),
            nullable=True,
        ),
        sa.Column("adapter_step", sa.Integer(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column(
            "file_size_bytes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index(
        "idx_merged_models_project", "merged_models", ["project_id"]
    )
    op.create_index(
        "idx_merged_models_source_run", "merged_models", ["source_run_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_merged_models_source_run", table_name="merged_models")
    op.drop_index("idx_merged_models_project", table_name="merged_models")
    op.drop_table("merged_models")
