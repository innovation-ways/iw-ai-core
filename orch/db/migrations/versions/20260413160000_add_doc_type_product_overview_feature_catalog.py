"""add_doc_type_product_overview_feature_catalog

Revision ID: add_doc_type_product_overview_feature_catalog
Revises: add_doc_broken_links
Create Date: 2026-04-13 16:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

revision: str = "add_doc_types_functional"
down_revision: str | None = "add_doc_broken_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE doc_type ADD VALUE IF NOT EXISTS 'product_overview'")
    op.execute("ALTER TYPE doc_type ADD VALUE IF NOT EXISTS 'feature_catalog'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum.
    # To roll back, recreate the type without the new values (requires no rows use them).
    pass
