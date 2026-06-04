"""add_doc_type_research

Revision ID: add_doc_type_research
Revises: add_doc_types_functional
Create Date: 2026-04-14 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

revision: str = "add_doc_type_research"
down_revision: str | None = "add_doc_types_functional"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE doc_type ADD VALUE IF NOT EXISTS 'research'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum.
    pass
