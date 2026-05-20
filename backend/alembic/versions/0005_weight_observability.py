"""weight observability: layers_json on model_profiles, new weight_snapshots table

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-20 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "model_profiles",
        sa.Column("layers_json", sa.Text(), nullable=True),
    )
    op.create_table(
        "weight_snapshots",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("layer_name", sa.Text(), nullable=False),
        sa.Column("mean", sa.Float(), nullable=False),
        sa.Column("std", sa.Float(), nullable=False),
        sa.Column("norm", sa.Float(), nullable=False),
        sa.Column("min_val", sa.Float(), nullable=False),
        sa.Column("max_val", sa.Float(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("run_id", "step", "layer_name"),
    )
    op.create_index(
        "idx_weight_snapshots_run_layer_step",
        "weight_snapshots",
        ["run_id", "layer_name", "step"],
    )


def downgrade() -> None:
    op.drop_index("idx_weight_snapshots_run_layer_step", table_name="weight_snapshots")
    op.drop_table("weight_snapshots")
    op.drop_column("model_profiles", "layers_json")
