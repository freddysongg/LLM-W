"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-07 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "config_versions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("yaml_blob", sa.Text(), nullable=False),
        sa.Column("yaml_hash", sa.Text(), nullable=False),
        sa.Column("diff_from_prev", sa.Text(), nullable=True),
        sa.Column("source_tag", sa.Text(), nullable=False),
        sa.Column("source_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version_number"),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("directory_path", sa.Text(), nullable=False),
        sa.Column("active_config_version_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["active_config_version_id"], ["config_versions.id"], use_alter=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "model_profiles",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column("architecture_name", sa.Text(), nullable=True),
        sa.Column("parameter_count", sa.Integer(), nullable=True),
        sa.Column("trainable_count", sa.Integer(), nullable=True),
        sa.Column("tokenizer_type", sa.Text(), nullable=True),
        sa.Column("vocab_size", sa.Integer(), nullable=True),
        sa.Column("max_position_embeddings", sa.Integer(), nullable=True),
        sa.Column("hidden_size", sa.Integer(), nullable=True),
        sa.Column("num_layers", sa.Integer(), nullable=True),
        sa.Column("num_attention_heads", sa.Integer(), nullable=True),
        sa.Column("capabilities_json", sa.Text(), nullable=True),
        sa.Column("resource_estimate_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "dataset_profiles",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("dataset_id", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=True),
        sa.Column("train_size", sa.Integer(), nullable=True),
        sa.Column("eval_size", sa.Integer(), nullable=True),
        sa.Column("field_mapping_json", sa.Text(), nullable=True),
        sa.Column("token_stats_json", sa.Text(), nullable=True),
        sa.Column("quality_warnings", sa.Text(), nullable=True),
        sa.Column("format", sa.Text(), nullable=False, server_default="default"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("config_version_id", sa.Text(), nullable=False),
        sa.Column("parent_run_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("current_stage", sa.Text(), nullable=True),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_steps", sa.Integer(), nullable=True),
        sa.Column("progress_pct", sa.Real(), nullable=False, server_default="0.0"),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("failure_stage", sa.Text(), nullable=True),
        sa.Column("last_checkpoint_path", sa.Text(), nullable=True),
        sa.Column("heartbeat_path", sa.Text(), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["config_version_id"], ["config_versions.id"]),
        sa.ForeignKeyConstraint(["parent_run_id"], ["runs.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_runs_project", "runs", ["project_id"])
    op.create_index("idx_runs_status", "runs", ["status"])

    op.create_table(
        "run_stages",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("stage_name", sa.Text(), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("warnings_json", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("log_tail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_run_stages_run", "run_stages", ["run_id"])

    op.create_table(
        "metric_points",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("epoch", sa.Real(), nullable=True),
        sa.Column("metric_name", sa.Text(), nullable=False),
        sa.Column("metric_value", sa.Real(), nullable=False),
        sa.Column("stage_name", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_metrics_run_step", "metric_points", ["run_id", "step"])
    op.create_index("idx_metrics_run_name", "metric_points", ["run_id", "metric_name"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("is_retained", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_artifacts_run", "artifacts", ["run_id"])
    op.create_index("idx_artifacts_type", "artifacts", ["artifact_type"])

    op.create_table(
        "ai_suggestions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("source_run_id", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("config_diff", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("expected_effect", sa.Text(), nullable=True),
        sa.Column("tradeoffs", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Real(), nullable=True),
        sa.Column("risk_level", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("applied_config_version_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("resolved_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["applied_config_version_id"], ["config_versions.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["source_run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_suggestions_project", "ai_suggestions", ["project_id"])
    op.create_index("idx_suggestions_status", "ai_suggestions", ["status"])

    op.create_table(
        "decision_logs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("before_state", sa.Text(), nullable=True),
        sa.Column("after_state", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_decisions_project", "decision_logs", ["project_id"])

    op.create_table(
        "activation_snapshots",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_step", sa.Integer(), nullable=False),
        sa.Column("layer_name", sa.Text(), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=False),
        sa.Column("full_tensor_path", sa.Text(), nullable=True),
        sa.Column("sample_input_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_activations_run", "activation_snapshots", ["run_id"])
    op.create_index("idx_activations_layer", "activation_snapshots", ["layer_name"])

    op.create_table(
        "storage_records",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("total_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_computed_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_storage_project", "storage_records", ["project_id"])


def downgrade() -> None:
    op.drop_index("idx_storage_project", table_name="storage_records")
    op.drop_table("storage_records")
    op.drop_index("idx_activations_layer", table_name="activation_snapshots")
    op.drop_index("idx_activations_run", table_name="activation_snapshots")
    op.drop_table("activation_snapshots")
    op.drop_index("idx_decisions_project", table_name="decision_logs")
    op.drop_table("decision_logs")
    op.drop_index("idx_suggestions_status", table_name="ai_suggestions")
    op.drop_index("idx_suggestions_project", table_name="ai_suggestions")
    op.drop_table("ai_suggestions")
    op.drop_index("idx_artifacts_type", table_name="artifacts")
    op.drop_index("idx_artifacts_run", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("idx_metrics_run_name", table_name="metric_points")
    op.drop_index("idx_metrics_run_step", table_name="metric_points")
    op.drop_table("metric_points")
    op.drop_index("idx_run_stages_run", table_name="run_stages")
    op.drop_table("run_stages")
    op.drop_index("idx_runs_status", table_name="runs")
    op.drop_index("idx_runs_project", table_name="runs")
    op.drop_table("runs")
    op.drop_table("dataset_profiles")
    op.drop_table("model_profiles")
    op.drop_table("projects")
    op.drop_table("config_versions")
