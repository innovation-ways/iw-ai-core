"""add project oss job

Revision ID: 13014259ab68
Revises: 637c16395a0b
Create Date: 2026-04-23 06:18:29.805888

Adds project_oss_job table for async OSS scan/prepare/publish/install job tracking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "13014259ab68"
down_revision: str | None = "637c16395a0b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    project_oss_job_kind = postgresql.ENUM(
        "scan",
        "prepare",
        "publish",
        "install",
        name="project_oss_job_kind",
        create_type=False,
    )
    project_oss_job_status = postgresql.ENUM(
        "queued",
        "running",
        "complete",
        "error",
        "cancelled",
        name="project_oss_job_status",
        create_type=False,
    )

    for enum_type in [project_oss_job_kind, project_oss_job_status]:
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "project_oss_job",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "project_id",
            sa.Text(),
            nullable=False,
            comment="FK to projects.id",
        ),
        sa.Column("kind", project_oss_job_kind, nullable=False),
        sa.Column(
            "status",
            project_oss_job_status,
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column(
            "worktree_path",
            sa.Text(),
            nullable=True,
            comment="Temp path for prepare/publish; NULL for scan/install",
        ),
        sa.Column(
            "scan_id",
            sa.BigInteger(),
            nullable=True,
            comment="FK to oss_scan.id when kind=scan; NULL otherwise",
        ),
        sa.Column(
            "stdout_tail",
            sa.Text(),
            nullable=True,
            comment="Last 16KB of combined stdout/stderr",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scan_id"], ["oss_scan.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="Async OSS scan/prepare/publish/install job tracking",
    )

    op.create_index(
        "ix_project_oss_job_project_created",
        "project_oss_job",
        ["project_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_project_oss_job_status", "project_oss_job", ["status"])


def downgrade() -> None:
    op.drop_index("ix_project_oss_job_status", table_name="project_oss_job")
    op.drop_index("ix_project_oss_job_project_created", table_name="project_oss_job")
    op.drop_table("project_oss_job")

    op.execute("DROP TYPE IF EXISTS project_oss_job_status;")
    op.execute("DROP TYPE IF EXISTS project_oss_job_kind;")
