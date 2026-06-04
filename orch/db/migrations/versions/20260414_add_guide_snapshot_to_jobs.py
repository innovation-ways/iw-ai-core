"""Add guide_snapshot to doc_generation_jobs.

Revision ID: add_guide_snapshot_to_jobs
Revises: add_doc_type_guides
Create Date: 2026-04-14 00:00:00.000000

Guide content snapshotted at job creation time for audit purposes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

revision: str = "add_guide_snapshot_to_jobs"
down_revision: str | None = "add_doc_type_guides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE doc_generation_jobs ADD COLUMN guide_snapshot TEXT")
    op.execute(
        "COMMENT ON COLUMN doc_generation_jobs.guide_snapshot IS 'Guide content snapshotted at job creation time for audit purposes.'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE doc_generation_jobs DROP COLUMN IF EXISTS guide_snapshot")
