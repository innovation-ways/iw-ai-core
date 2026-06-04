"""add test_runs table

Revision ID: 80f00b5e7fb3
Revises: 011e2a69dbd8
Create Date: 2026-04-09 23:29:10.725023

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "80f00b5e7fb3"
down_revision: str | None = "011e2a69dbd8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "test_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Text(),
            nullable=False,
            comment="Project that owns this test run",
        ),
        sa.Column(
            "category",
            sa.Text(),
            nullable=False,
            comment="Test category key (e.g. 'unit', 'integration', 'e2e')",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "passed",
                "failed",
                "cancelled",
                "error",
                name="test_run_status",
            ),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("command", sa.Text(), nullable=False, comment="Shell command executed"),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_secs", sa.Float(), nullable=True),
        sa.Column(
            "pid",
            sa.Integer(),
            nullable=True,
            comment="OS process ID (for kill support)",
        ),
        sa.Column(
            "log_path",
            sa.Text(),
            nullable=True,
            comment="Absolute path to captured stdout/stderr log",
        ),
        sa.Column(
            "allure_results_dir",
            sa.Text(),
            nullable=True,
            comment="Path to allure-results directory for this run",
        ),
        sa.Column(
            "allure_report_dir",
            sa.Text(),
            nullable=True,
            comment="Path to generated allure-report directory",
        ),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Parsed Allure widgets/summary.json content",
        ),
        sa.Column(
            "triggered_by",
            sa.Text(),
            server_default=sa.text("'user'"),
            nullable=False,
            comment="Who triggered: user, scheduled",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Test execution runs launched from the dashboard. Append-only.",
    )
    op.create_index(
        "idx_test_runs_project_created",
        "test_runs",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_test_runs_project_status",
        "test_runs",
        ["project_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_test_runs_project_status", table_name="test_runs")
    op.drop_index("idx_test_runs_project_created", table_name="test_runs")
    op.drop_table("test_runs")
    sa.Enum(name="test_run_status").drop(op.get_bind(), checkfirst=True)
