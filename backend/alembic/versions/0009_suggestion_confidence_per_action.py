"""suggestion confidence_per_action_json column

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-20 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_suggestions",
        sa.Column("confidence_per_action_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_suggestions", "confidence_per_action_json")
