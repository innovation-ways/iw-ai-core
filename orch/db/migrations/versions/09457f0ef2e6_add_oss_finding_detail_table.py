"""add oss_finding_detail table

Revision ID: 09457f0ef2e6
Revises: cr00024warned50
Create Date: 2026-04-27 21:23:56.504571

Per-result rows for multi-result OSS findings (e.g. each gitleaks hit). One
``oss_finding`` row aggregates the count and aggregate evidence; one
``oss_finding_detail`` row per underlying match carries the file path, line
number, rule id, and a redacted snippet for display in the dashboard modal.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "09457f0ef2e6"
down_revision: str | None = "cr00024warned50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oss_finding_detail",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("finding_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "ordinal",
            sa.Integer(),
            nullable=False,
            comment="Stable order from the source SARIF",
        ),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column(
            "snippet_masked",
            sa.Text(),
            nullable=True,
            comment="Secret value with middle bytes redacted",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["finding_id"], ["oss_finding.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Per-result rows for a multi-result OSS finding",
    )
    op.create_index(
        "ix_oss_finding_detail_finding",
        "oss_finding_detail",
        ["finding_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_oss_finding_detail_finding", table_name="oss_finding_detail")
    op.drop_table("oss_finding_detail")
