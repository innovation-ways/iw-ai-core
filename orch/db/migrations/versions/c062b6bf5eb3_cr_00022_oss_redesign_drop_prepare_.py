"""CR-00022 OSS redesign: drop prepare/publish, add auto_apply_safe

Revision ID: c062b6bf5eb3
Revises: 550aecbbd42b
Create Date: 2026-04-26 11:32:24.153769

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c062b6bf5eb3"
down_revision: str | Sequence[str] | None = "550aecbbd42b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Pre-delete rows referencing dropped enum values
    op.execute("DELETE FROM project_oss_job WHERE kind IN ('prepare','publish')")
    op.execute("DELETE FROM oss_scan WHERE mode IN ('make_oss','publish')")
    op.execute("DELETE FROM project_oss_job WHERE status IN ('awaiting_review','discarded')")

    # 2. Drop columns from project_oss_job
    op.drop_column("project_oss_job", "files_changed_summary")
    op.drop_column("project_oss_job", "commit_sha")
    op.drop_column("project_oss_job", "branch_name")
    op.drop_column("project_oss_job", "worktree_path")

    # 3. Add column to oss_finding
    op.add_column(
        "oss_finding",
        sa.Column("auto_apply_safe", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # 4. Recreate project_oss_job_kind enum (drop prepare/publish, add fix)
    op.execute("CREATE TYPE project_oss_job_kind_new AS ENUM ('scan','install','fix')")
    op.execute(
        "ALTER TABLE project_oss_job ALTER COLUMN kind TYPE project_oss_job_kind_new "
        "USING kind::text::project_oss_job_kind_new"
    )
    op.execute("DROP TYPE project_oss_job_kind")
    op.execute("ALTER TYPE project_oss_job_kind_new RENAME TO project_oss_job_kind")

    # 5. Recreate ossscan_mode enum (drop make_oss/publish)
    op.execute("CREATE TYPE ossscan_mode_new AS ENUM ('scan')")
    op.execute("ALTER TABLE oss_scan ALTER COLUMN mode DROP DEFAULT")
    op.execute(
        "ALTER TABLE oss_scan ALTER COLUMN mode TYPE ossscan_mode_new "
        "USING mode::text::ossscan_mode_new"
    )
    op.execute("ALTER TABLE oss_scan ALTER COLUMN mode SET DEFAULT 'scan'::ossscan_mode_new")
    op.execute("DROP TYPE ossscan_mode")
    op.execute("ALTER TYPE ossscan_mode_new RENAME TO ossscan_mode")

    # 6. Recreate project_oss_job_status enum (drop awaiting_review/discarded)
    op.execute(
        "CREATE TYPE project_oss_job_status_new AS ENUM "
        "('queued','running','complete','error','cancelled')"
    )
    op.execute("ALTER TABLE project_oss_job ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE project_oss_job ALTER COLUMN status TYPE project_oss_job_status_new "
        "USING status::text::project_oss_job_status_new"
    )
    op.execute(
        "ALTER TABLE project_oss_job ALTER COLUMN status SET DEFAULT 'queued'::project_oss_job_status_new"
    )
    op.execute("DROP TYPE project_oss_job_status")
    op.execute("ALTER TYPE project_oss_job_status_new RENAME TO project_oss_job_status")


def downgrade() -> None:
    # 1. Remove auto_apply_safe column from oss_finding
    op.drop_column("oss_finding", "auto_apply_safe")

    # 2. Recreate project_oss_job columns that were dropped
    op.add_column(
        "project_oss_job",
        sa.Column("worktree_path", sa.Text(), nullable=True),
    )
    op.add_column(
        "project_oss_job",
        sa.Column("files_changed_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "project_oss_job",
        sa.Column("commit_sha", sa.Text(), nullable=True),
    )
    op.add_column(
        "project_oss_job",
        sa.Column("branch_name", sa.Text(), nullable=True),
    )

    # 3. Recreate the old project_oss_job_kind enum with original values
    # PostgreSQL doesn't support removing enum values, so we just recreate the type
    op.execute("DROP TYPE IF EXISTS project_oss_job_kind_old")
    op.execute("ALTER TYPE project_oss_job_kind RENAME TO project_oss_job_kind_old")
    op.execute("CREATE TYPE project_oss_job_kind AS ENUM ('scan','prepare','publish','install')")
    op.execute(
        "ALTER TABLE project_oss_job ALTER COLUMN kind TYPE project_oss_job_kind "
        "USING kind::text::project_oss_job_kind"
    )
    op.execute("DROP TYPE project_oss_job_kind_old")

    # 4. Recreate the old ossscan_mode enum with original values
    op.execute("DROP TYPE IF EXISTS ossscan_mode_old")
    op.execute("ALTER TYPE ossscan_mode RENAME TO ossscan_mode_old")
    op.execute("CREATE TYPE ossscan_mode AS ENUM ('scan','make_oss','publish')")
    op.execute("ALTER TABLE oss_scan ALTER COLUMN mode DROP DEFAULT")
    op.execute(
        "ALTER TABLE oss_scan ALTER COLUMN mode TYPE ossscan_mode USING mode::text::ossscan_mode"
    )
    op.execute("ALTER TABLE oss_scan ALTER COLUMN mode SET DEFAULT 'scan'::ossscan_mode")
    op.execute("DROP TYPE ossscan_mode_old")

    # 5. Restore the old project_oss_job_status enum with original values
    # Note: awaiting_review and discarded values are kept as orphans since PostgreSQL
    # doesn't support removing enum values
    op.execute("DROP TYPE IF EXISTS project_oss_job_status_old")
    op.execute("ALTER TYPE project_oss_job_status RENAME TO project_oss_job_status_old")
    op.execute(
        "CREATE TYPE project_oss_job_status AS ENUM "
        "('queued','running','complete','error','cancelled','awaiting_review','discarded')"
    )
    op.execute("ALTER TABLE project_oss_job ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE project_oss_job ALTER COLUMN status TYPE project_oss_job_status "
        "USING status::text::project_oss_job_status"
    )
    op.execute(
        "ALTER TABLE project_oss_job ALTER COLUMN status SET DEFAULT 'queued'::project_oss_job_status"
    )
    op.execute("DROP TYPE project_oss_job_status_old")
