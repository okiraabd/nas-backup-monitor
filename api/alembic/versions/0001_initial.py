"""initial schema — users, backup_logs, metrics, collector_runs, reports

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # --- backup_logs ---
    op.create_table(
        "backup_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nas_id", sa.String(64), nullable=False),
        sa.Column("job_name", sa.String(128), nullable=False),
        sa.Column("source_path", sa.String(512), nullable=True),
        sa.Column("source_ip", sa.String(64), nullable=True),
        sa.Column("destination_target", sa.String(128), nullable=True),
        sa.Column("backup_engine", sa.String(32), nullable=False, server_default="kopia"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("snapshot_id", sa.String(128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("total_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("total_files", sa.Integer(), nullable=True),
        sa.Column("changed_file_count", sa.Integer(), nullable=True),
        sa.Column("cached_files", sa.Integer(), nullable=True),
        sa.Column("non_cached_files", sa.Integer(), nullable=True),
        sa.Column("dir_count", sa.Integer(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=True),
        sa.Column("ignored_error_count", sa.Integer(), nullable=True),
        sa.Column("retention_reason", postgresql.JSONB(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column("reported_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("acknowledged_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_backup_logs_nas_id", "backup_logs", ["nas_id"])
    op.create_index("ix_backup_logs_job_name", "backup_logs", ["job_name"])
    op.create_index("ix_backup_logs_status", "backup_logs", ["status"])
    op.create_index("ix_backup_logs_created_at", "backup_logs", ["created_at"])

    # --- metrics ---
    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("metric_name", sa.String(64), nullable=False),
        sa.Column("metric_value", sa.Numeric(), nullable=True),
        sa.Column("metric_text", sa.String(255), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("collected_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_metrics_source_name_time", "metrics", ["source_id", "metric_name", "collected_at"])
    op.create_index("ix_metrics_type_source_time", "metrics", ["source_type", "source_id", "collected_at"])

    # --- collector_runs ---
    op.create_table(
        "collector_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False, server_default="demo"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("total_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_collector_runs_created_at", "collector_runs", ["created_at"])

    # --- reports ---
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("nas_filter", sa.String(64), nullable=True),
        sa.Column("generated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("file_path", sa.String(512), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_index("ix_collector_runs_created_at", table_name="collector_runs")
    op.drop_table("collector_runs")
    op.drop_index("ix_metrics_type_source_time", table_name="metrics")
    op.drop_index("ix_metrics_source_name_time", table_name="metrics")
    op.drop_table("metrics")
    for idx in (
        "ix_backup_logs_created_at",
        "ix_backup_logs_status",
        "ix_backup_logs_job_name",
        "ix_backup_logs_nas_id",
    ):
        op.drop_index(idx, table_name="backup_logs")
    op.drop_table("backup_logs")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
