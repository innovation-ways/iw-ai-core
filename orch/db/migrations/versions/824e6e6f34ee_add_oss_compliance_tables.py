"""add oss compliance tables

Revision ID: 824e6e6f34ee
Revises: 4d5e6f7a8b9c
Create Date: 2026-04-21 22:29:35.484520

Adds project.oss_enabled column and three tables: oss_scan, oss_finding, oss_tool_run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "824e6e6f34ee"
down_revision: str | None = "4d5e6f7a8b9c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- ENUM types ---
    ossscan_status = postgresql.ENUM(
        "pending", "running", "complete", "error", name="ossscan_status", create_type=False
    )
    ossscan_mode = postgresql.ENUM(
        "scan", "make_oss", "publish", name="ossscan_mode", create_type=False
    )
    osspill_color = postgresql.ENUM(
        "green", "yellow", "red", "gray", name="osspill_color", create_type=False
    )
    ossfinding_severity = postgresql.ENUM(
        "MUST", "SHOULD", "MAY", "INFO", name="ossfinding_severity", create_type=False
    )
    ossfinding_status = postgresql.ENUM(
        "pass_status", "fail", "skip", "human_required", name="ossfinding_status", create_type=False
    )
    osstoolrun_status = postgresql.ENUM(
        "ok", "failed", "missing", "skipped", name="osstoolrun_status", create_type=False
    )

    for enum_type in [
        ossscan_status,
        ossscan_mode,
        osspill_color,
        ossfinding_severity,
        ossfinding_status,
        osstoolrun_status,
    ]:
        enum_type.create(op.get_bind(), checkfirst=True)

    # --- Add oss_enabled to projects ---
    op.add_column(
        "projects",
        sa.Column(
            "oss_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether OSS compliance scanning is enabled for this project",
        ),
    )

    # --- oss_scan ---
    op.create_table(
        "oss_scan",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False, comment="FK to projects.id"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="When the scan started",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the scan finished",
        ),
        sa.Column("status", ossscan_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column(
            "mode",
            ossscan_mode,
            nullable=False,
            server_default=sa.text("'scan'"),
        ),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column(
            "head_sha",
            sa.Text(),
            nullable=True,
            comment="Git HEAD SHA at scan start",
        ),
        sa.Column("pill_color", osspill_color, nullable=True),
        sa.Column(
            "summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Counts-by-severity summary",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Error message if status='error'",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="OSS compliance scan runs",
    )
    op.create_index(
        "ix_oss_scan_project_started",
        "oss_scan",
        ["project_id", sa.text("started_at DESC")],
    )

    # --- oss_finding ---
    op.create_table(
        "oss_finding",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("scan_id", sa.BigInteger(), nullable=False, comment="FK to oss_scan.id"),
        sa.Column(
            "check_id",
            sa.Text(),
            nullable=False,
            comment="Check identifier (e.g., OSS-LIC-01)",
        ),
        sa.Column("severity", ossfinding_severity, nullable=False),
        sa.Column("status", ossfinding_status, nullable=False),
        sa.Column(
            "domain",
            sa.Text(),
            nullable=False,
            comment="Domain: license, secrets, etc.",
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column(
            "auto_fix_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "osps_control",
            sa.Text(),
            nullable=True,
            comment="OSPS control reference",
        ),
        sa.Column("tool", sa.Text(), nullable=True),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["scan_id"], ["oss_scan.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Individual OSS compliance findings",
    )
    op.create_index("ix_oss_finding_scan", "oss_finding", ["scan_id"])
    op.create_index(
        "ix_oss_finding_scan_sev_stat",
        "oss_finding",
        ["scan_id", "severity", "status"],
    )

    # --- oss_tool_run ---
    op.create_table(
        "oss_tool_run",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("scan_id", sa.BigInteger(), nullable=False, comment="FK to oss_scan.id"),
        sa.Column("tool", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=True),
        sa.Column("status", osstoolrun_status, nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("runtime_ms", sa.Integer(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column(
            "output_summary",
            sa.Text(),
            nullable=True,
            comment="First 2KB of stdout/stderr",
        ),
        sa.ForeignKeyConstraint(["scan_id"], ["oss_scan.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Tier-1 tool execution records within an OSS scan",
    )
    op.create_index("ix_oss_tool_run_scan", "oss_tool_run", ["scan_id"])


def downgrade() -> None:
    op.drop_index("ix_oss_tool_run_scan", table_name="oss_tool_run")
    op.drop_table("oss_tool_run")

    op.drop_index("ix_oss_finding_scan_sev_stat", table_name="oss_finding")
    op.drop_index("ix_oss_finding_scan", table_name="oss_finding")
    op.drop_table("oss_finding")

    op.drop_index("ix_oss_scan_project_started", table_name="oss_scan")
    op.drop_table("oss_scan")

    op.drop_column("projects", "oss_enabled")

    for enum_name in [
        "osstoolrun_status",
        "ossfinding_status",
        "ossfinding_severity",
        "osspill_color",
        "ossscan_mode",
        "ossscan_status",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name};")
