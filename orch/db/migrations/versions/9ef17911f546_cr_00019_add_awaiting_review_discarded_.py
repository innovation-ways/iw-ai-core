"""CR-00019: add awaiting_review/discarded to project_oss_job_status enum, add columns to project_oss_job and oss_finding

Revision ID: 9ef17911f546
Revises: 1fb2eb17b580
Create Date: 2026-04-24 09:34:03.067749

Adds two new status values to project_oss_job_status (awaiting_review, discarded)
for the reviewable worktree lifecycle. Also adds columns to project_oss_job
(base_sha, branch_name, commit_sha, files_changed_summary) and oss_finding (rationale).

PostgreSQL does not support removing enum values, so downgrade is a no-op for the enum.
Columns are dropped in downgrade (fully reversible).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9ef17911f546"
down_revision: str | None = "1fb2eb17b580"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE project_oss_job_status ADD VALUE IF NOT EXISTS 'awaiting_review'")
    op.execute("ALTER TYPE project_oss_job_status ADD VALUE IF NOT EXISTS 'discarded'")

    op.add_column(
        "project_oss_job",
        sa.Column(
            "base_sha", sa.Text(), nullable=True, comment="Git HEAD SHA when Prepare was fired"
        ),
    )
    op.add_column(
        "project_oss_job",
        sa.Column(
            "branch_name",
            sa.Text(),
            nullable=True,
            comment="Prep branch name (iw-oss-publish/prep-<job_id>)",
        ),
    )
    op.add_column(
        "project_oss_job",
        sa.Column("commit_sha", sa.Text(), nullable=True, comment="Commit SHA on the prep branch"),
    )
    op.add_column(
        "project_oss_job",
        sa.Column(
            "files_changed_summary",
            sa.Text(),
            nullable=True,
            comment="git diff --stat at commit time",
        ),
    )

    op.add_column(
        "oss_finding",
        sa.Column("rationale", sa.Text(), nullable=True, comment="Per-check rationale paragraph"),
    )


def downgrade() -> None:
    op.drop_column("oss_finding", "rationale")

    op.drop_column("project_oss_job", "files_changed_summary")
    op.drop_column("project_oss_job", "commit_sha")
    op.drop_column("project_oss_job", "branch_name")
    op.drop_column("project_oss_job", "base_sha")
