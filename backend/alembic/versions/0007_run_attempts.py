"""run attempts table for oom fallback chain

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-20 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "run_attempts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Text(),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_index", sa.Integer(), nullable=False),
        sa.Column("gpu_type", sa.Text(), nullable=True),
        sa.Column("device", sa.Text(), nullable=True),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("ended_at", sa.Text(), nullable=True),
        sa.Column("exit_reason", sa.Text(), nullable=True),
        sa.Column("cost_estimate_usd", sa.Float(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "run_id",
            "attempt_index",
            name="uq_run_attempts_run_id_attempt_index",
        ),
    )
    op.create_index("idx_run_attempts_run_id", "run_attempts", ["run_id"])


def downgrade() -> None:
    op.drop_index("idx_run_attempts_run_id", table_name="run_attempts")
    op.drop_table("run_attempts")
