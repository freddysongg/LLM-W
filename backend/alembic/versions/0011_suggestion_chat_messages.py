"""suggestion chat messages table

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-20 00:00:01.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "suggestion_chat_messages",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "suggestion_id",
            sa.Text(),
            sa.ForeignKey("ai_suggestions.id"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index(
        "idx_suggestion_chat_messages_suggestion",
        "suggestion_chat_messages",
        ["suggestion_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_suggestion_chat_messages_suggestion",
        table_name="suggestion_chat_messages",
    )
    op.drop_table("suggestion_chat_messages")
