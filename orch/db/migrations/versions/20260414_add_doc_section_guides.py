"""add_doc_section_guides

Revision ID: add_doc_section_guides
Revises: add_doc_type_research
Create Date: 2026-04-14 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "add_doc_section_guides"
down_revision: str | None = "add_doc_type_research"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "doc_section_guides",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "doc_id",
            sa.Text(),
            nullable=False,
            comment="FK to project_docs.id (composite: project_id:doc_id). ON DELETE CASCADE.",
        ),
        sa.Column(
            "section_name",
            sa.Text(),
            nullable=False,
            comment="H2 heading text, or 'Document' if no H2 headings exist.",
        ),
        sa.Column(
            "guide_md",
            sa.Text(),
            nullable=False,
            comment="Markdown editorial guidelines for this specific section.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Timestamp of last guide edit.",
        ),
        sa.ForeignKeyConstraint(["doc_id"], ["project_docs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_doc_section_guides_doc_id", "doc_section_guides", ["doc_id"])
    op.create_unique_index(
        "uq_doc_section_guides_doc_section",
        "doc_section_guides",
        ["doc_id", "section_name"],
    )
    op.execute(
        "COMMENT ON TABLE doc_section_guides IS 'Per-section editorial guidelines keyed by (doc_id, section_name).';"
    )


def downgrade() -> None:
    op.drop_table("doc_section_guides")
