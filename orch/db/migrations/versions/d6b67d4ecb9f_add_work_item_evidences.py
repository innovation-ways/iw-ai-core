"""add work_item_evidences

Revision ID: d6b67d4ecb9f
Revises: 9ef17911f546, 74f9b2350784
Create Date: 2026-04-24 18:42:51.508091

Add work_item_evidences table for storing evidence screenshots/snapshots
as durable BLOBs (CR-00020). Ingested at two lifecycle points:
- phase='pre': when a work item is approved (iw approve)
- phase='post': when a browser_verification step completes (iw step-done)

The FK to work_items has NO cascade — evidences survive work_item deletion
so that archived items still display their evidences in the dashboard.

This revision also linearises two parallel heads left on main after F-00060
(74f9b2350784 doc_index_jobs) merged without rebasing on top of CR-00019
(9ef17911f546). Both are declared as down_revisions so d6b67d4ecb9f becomes
the single head.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6b67d4ecb9f"
down_revision: tuple[str, ...] | str | None = ("9ef17911f546", "74f9b2350784")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "DO $$ "
        "BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'evidence_phase') THEN "
        "CREATE TYPE evidence_phase AS ENUM ('pre', 'post'); "
        "END IF; "
        "END $$"
    )

    op.create_table(
        "work_item_evidences",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("work_item_id", sa.Text(), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("step_id", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id", "work_item_id"],
            ["work_items.project_id", "work_items.id"],
            name="fk_evidence_work_item",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "work_item_id", "phase", "filename", name="uq_evidence_per_file"
        ),
        comment="Work item evidence screenshots and snapshots as durable BLOBs (CR-00020)",
    )
    op.create_index(
        "ix_evidence_project_item_phase",
        "work_item_evidences",
        ["project_id", "work_item_id", "phase"],
        unique=False,
    )
    op.execute(
        "ALTER TABLE work_item_evidences ALTER COLUMN phase TYPE evidence_phase "
        "USING phase::evidence_phase"
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_project_item_phase", table_name="work_item_evidences")
    op.drop_table("work_item_evidences")
    op.execute("DROP TYPE IF EXISTS evidence_phase")
