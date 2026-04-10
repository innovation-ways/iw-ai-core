"""Add 'cancelled' value to work_item_status enum.

Revision ID: 6d7d3b4a3b83
Revises: 80f00b5e7fb3
Create Date: 2026-04-10 11:48:49.434539

PostgreSQL does not allow removing enum values, so the downgrade is a no-op.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6d7d3b4a3b83"
down_revision: str | None = "80f00b5e7fb3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE work_item_status ADD VALUE IF NOT EXISTS 'cancelled' AFTER 'paused'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type.
    pass
