"""Add 'merging' value to batch_item_status enum.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-08 00:00:00.000000

PostgreSQL does not allow removing enum values, so the downgrade is a no-op.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ADD VALUE is not transactional in PostgreSQL — IF NOT EXISTS makes it idempotent.
    op.execute("ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'merging' AFTER 'completed'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type.
    # A no-op downgrade is intentional.
    pass
