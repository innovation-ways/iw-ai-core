"""add functional_doc columns to work_items

Revision ID: 1fb2eb17b580
Revises: 3035dfc20db5
Create Date: 2026-04-24 06:09:56.207345

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

from orch.db.models import (
    FUNCTIONAL_DOC_FTS_FUNCTION_SQL,
    FUNCTIONAL_DOC_FTS_TRIGGER_SQL,
)

revision: str = "1fb2eb17b580"
down_revision: Union[str, Sequence[str], None] = "3035dfc20db5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "work_items",
        sa.Column(
            "functional_doc_path",
            sa.Text(),
            nullable=True,
            comment="Relative path to functional design doc in project repo (active items)",
        ),
    )
    op.add_column(
        "work_items",
        sa.Column(
            "functional_doc_content",
            sa.Text(),
            nullable=True,
            comment=(
                "Full markdown of functional design doc "
                "(Tier 1 — stored on archive for instant dashboard rendering)"
            ),
        ),
    )
    op.add_column(
        "work_items",
        sa.Column(
            "functional_doc_search",
            postgresql.TSVECTOR(),
            nullable=True,
            comment="PostgreSQL tsvector for full-text search across functional design docs",
        ),
    )
    op.execute(text(FUNCTIONAL_DOC_FTS_FUNCTION_SQL))
    op.execute(text(FUNCTIONAL_DOC_FTS_TRIGGER_SQL))
    op.create_index(
        "idx_work_items_functional_doc_search",
        "work_items",
        ["functional_doc_search"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_work_items_functional_doc_search",
        table_name="work_items",
        postgresql_using="gin",
    )
    op.execute(text("DROP TRIGGER IF EXISTS work_items_functional_doc_search_trg ON work_items;"))
    op.execute(text("DROP FUNCTION IF EXISTS work_items_functional_doc_search_update();"))
    op.drop_column("work_items", "functional_doc_search")
    op.drop_column("work_items", "functional_doc_content")
    op.drop_column("work_items", "functional_doc_path")
