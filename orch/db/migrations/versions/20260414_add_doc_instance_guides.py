"""Add doc_instance_guides table.

Revision ID: add_doc_instance_guides
Revises: add_guide_snapshot_to_jobs
Create Date: 2026-04-14 00:00:00.000000

Per-document editorial guide overrides — highest priority, overrides doc_type_guides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

revision: str = "add_doc_instance_guides"
down_revision: str | None = "add_guide_snapshot_to_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE doc_instance_guides (
            doc_id     TEXT PRIMARY KEY REFERENCES project_docs(id) ON DELETE CASCADE,
            guide_md   TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )"""
    )
    op.execute(
        "COMMENT ON TABLE doc_instance_guides IS 'Per-document editorial guide overrides — highest priority, overrides doc_type_guides.'"
    )
    op.execute(
        "COMMENT ON COLUMN doc_instance_guides.doc_id IS 'Composite PK matching project_docs.id (format: project_id:doc_id).'"
    )
    op.execute(
        "COMMENT ON COLUMN doc_instance_guides.guide_md IS 'Markdown editorial instructions specific to this document.'"
    )
    op.execute(
        "COMMENT ON COLUMN doc_instance_guides.updated_at IS 'Timestamp of last guide edit.'"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS doc_instance_guides")
