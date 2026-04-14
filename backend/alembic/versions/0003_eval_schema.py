"""eval schema

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-14 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rubrics",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("research_basis", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "rubric_versions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("rubric_id", sa.Text(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("yaml_blob", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("diff_from_prev", sa.Text(), nullable=True),
        sa.Column("calibration_metrics", sa.Text(), nullable=True),
        sa.Column(
            "calibration_status",
            sa.Text(),
            nullable=False,
            server_default="uncalibrated",
        ),
        sa.Column("judge_model_pin", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["rubric_id"], ["rubrics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rubric_id", "version_number"),
    )
    op.create_index("idx_rubric_versions_rubric", "rubric_versions", ["rubric_id"])

    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("training_run_id", sa.Text(), nullable=True),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("pass_rate", sa.Float(), nullable=True),
        sa.Column("total_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("max_cost_usd", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["training_run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_eval_runs_training_run", "eval_runs", ["training_run_id"])

    op.create_table(
        "eval_cases",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("eval_run_id", sa.Text(), nullable=False),
        sa.Column("case_input", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["eval_run_id"], ["eval_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_eval_cases_eval_run", "eval_cases", ["eval_run_id"])

    op.create_table(
        "eval_calls",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("eval_run_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("rubric_version_id", sa.Text(), nullable=False),
        sa.Column("judge_model", sa.Text(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("per_criterion", sa.Text(), nullable=True),
        sa.Column("response_hash", sa.Text(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("replayed_from_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["eval_cases.id"]),
        sa.ForeignKeyConstraint(["eval_run_id"], ["eval_runs.id"]),
        sa.ForeignKeyConstraint(["replayed_from_id"], ["eval_calls.id"]),
        sa.ForeignKeyConstraint(["rubric_version_id"], ["rubric_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_eval_calls_eval_run", "eval_calls", ["eval_run_id"])
    op.create_index("idx_eval_calls_case", "eval_calls", ["case_id"])
    op.create_index("idx_eval_calls_rubric_version", "eval_calls", ["rubric_version_id"])

    op.execute(
        """
        CREATE TRIGGER eval_calls_no_update
        BEFORE UPDATE ON eval_calls
        BEGIN
          SELECT RAISE(ABORT, 'eval_calls is append-only');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER eval_calls_no_delete
        BEFORE DELETE ON eval_calls
        BEGIN
          SELECT RAISE(ABORT, 'eval_calls is append-only');
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS eval_calls_no_delete")
    op.execute("DROP TRIGGER IF EXISTS eval_calls_no_update")
    op.drop_index("idx_eval_calls_rubric_version", table_name="eval_calls")
    op.drop_index("idx_eval_calls_case", table_name="eval_calls")
    op.drop_index("idx_eval_calls_eval_run", table_name="eval_calls")
    op.drop_table("eval_calls")
    op.drop_index("idx_eval_cases_eval_run", table_name="eval_cases")
    op.drop_table("eval_cases")
    op.drop_index("idx_eval_runs_training_run", table_name="eval_runs")
    op.drop_table("eval_runs")
    op.drop_index("idx_rubric_versions_rubric", table_name="rubric_versions")
    op.drop_table("rubric_versions")
    op.drop_table("rubrics")
