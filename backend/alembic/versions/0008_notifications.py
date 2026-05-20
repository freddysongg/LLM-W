"""notifications table

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-20 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("read_at", sa.Text(), nullable=True),
    )
    op.create_index("idx_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_notifications_created_at", table_name="notifications")
    op.drop_table("notifications")
