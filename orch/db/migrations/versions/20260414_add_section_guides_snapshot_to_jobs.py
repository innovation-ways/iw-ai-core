"""add_section_guides_snapshot_to_jobs

Revision ID: add_section_guides_snapshot_to_jobs
Revises: add_doc_section_guides
Create Date: 2026-04-14 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "add_section_guides_snapshot_to_jobs"
down_revision: str | None = "add_doc_section_guides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "doc_generation_jobs",
        sa.Column(
            "section_guides_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Section guides snapshotted at job creation: {section_name: guide_md, ...}.",
        ),
    )
    op.execute(
        "COMMENT ON COLUMN doc_generation_jobs.section_guides_snapshot IS 'Section guides snapshotted at job creation: {section_name: guide_md, ...}';"
    )


def downgrade() -> None:
    op.drop_column("doc_generation_jobs", "section_guides_snapshot")
