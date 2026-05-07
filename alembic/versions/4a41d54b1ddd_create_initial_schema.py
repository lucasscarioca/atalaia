"""create initial schema

Revision ID: 4a41d54b1ddd
Revises:
Create Date: 2026-03-23 20:31:14.411628

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4a41d54b1ddd"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_prefix"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_table(
        "eval_suites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "slug", name="uq_eval_suites_project_slug"),
    )
    op.create_table(
        "eval_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("suite_id", sa.Uuid(), nullable=False),
        sa.Column("case_key", sa.String(length=120), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("expected_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["suite_id"], ["eval_suites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("suite_id", "case_key", name="uq_eval_cases_suite_key"),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("suite_id", sa.Uuid(), nullable=False),
        sa.Column("reference_run_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("requested_by_token_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["suite_id"], ["eval_suites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reference_run_id"], ["runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_token_id"], ["api_tokens.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runs_project_created_at", "runs", ["project_id", "created_at"], unique=False)
    op.create_index("ix_runs_suite_created_at", "runs", ["suite_id", "created_at"], unique=False)
    op.create_index("ix_runs_status_created_at", "runs", ["status", "created_at"], unique=False)
    op.create_table(
        "run_case_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=True),
        sa.Column("case_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("expected_json", sa.JSON(), nullable=False),
        sa.Column("actual_json", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_run_case_results_latency_non_negative"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["eval_cases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "case_key", name="uq_run_case_results_run_case_key"),
    )
    op.create_index("ix_run_case_results_run_status", "run_case_results", ["run_id", "status"], unique=False)
    op.create_index("ix_run_case_results_run_created_at", "run_case_results", ["run_id", "created_at"], unique=False)
    op.create_table(
        "run_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_key", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("run_artifacts")
    op.drop_index("ix_run_case_results_run_created_at", table_name="run_case_results")
    op.drop_index("ix_run_case_results_run_status", table_name="run_case_results")
    op.drop_table("run_case_results")
    op.drop_index("ix_runs_status_created_at", table_name="runs")
    op.drop_index("ix_runs_suite_created_at", table_name="runs")
    op.drop_index("ix_runs_project_created_at", table_name="runs")
    op.drop_table("runs")
    op.drop_table("eval_cases")
    op.drop_table("eval_suites")
    op.drop_table("api_tokens")
    op.drop_table("projects")
