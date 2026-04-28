"""add_diagram_doc_type

Revision ID: add_diagram_doc_type
Revises: fdf63560ff02
Create Date: 2026-04-28 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

revision: str = "add_diagram_doc_type"
down_revision: str | None = "fdf63560ff02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE doc_type ADD VALUE IF NOT EXISTS 'diagram'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum.
    pass
