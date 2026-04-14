"""bench run metrics

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-14 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("run_type", sa.Text(), nullable=False, server_default="training"),
    )
    op.add_column("runs", sa.Column("device", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("tokens_per_sec", sa.Float(), nullable=True))
    op.add_column("runs", sa.Column("time_to_first_checkpoint_s", sa.Float(), nullable=True))
    op.add_column("runs", sa.Column("wall_clock_s", sa.Float(), nullable=True))
    op.add_column("runs", sa.Column("peak_memory_mb", sa.Float(), nullable=True))
    op.add_column("runs", sa.Column("heldout_perplexity", sa.Float(), nullable=True))
    op.add_column(
        "runs",
        sa.Column("cost_usd", sa.Float(), nullable=True, server_default="0.0"),
    )
    op.add_column("runs", sa.Column("judge_pass_rate", sa.Float(), nullable=True))
    op.add_column("runs", sa.Column("eval_split_hash", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("config_hash", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("metric_unavailable_reasons", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_column("metric_unavailable_reasons")
        batch_op.drop_column("config_hash")
        batch_op.drop_column("eval_split_hash")
        batch_op.drop_column("judge_pass_rate")
        batch_op.drop_column("cost_usd")
        batch_op.drop_column("heldout_perplexity")
        batch_op.drop_column("peak_memory_mb")
        batch_op.drop_column("wall_clock_s")
        batch_op.drop_column("time_to_first_checkpoint_s")
        batch_op.drop_column("tokens_per_sec")
        batch_op.drop_column("device")
        batch_op.drop_column("run_type")
