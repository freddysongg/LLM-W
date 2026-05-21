"""run execution metadata: environment + modal_gpu_type columns on runs

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-20 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("environment", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("modal_gpu_type", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "modal_gpu_type")
    op.drop_column("runs", "environment")
