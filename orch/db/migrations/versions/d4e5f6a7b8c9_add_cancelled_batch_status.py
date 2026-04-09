"""Add 'cancelled' value to batch_status enum.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-08 00:00:00.000000

PostgreSQL does not allow removing enum values, so the downgrade is a no-op.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE batch_status ADD VALUE IF NOT EXISTS 'cancelled' AFTER 'archived'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type.
    pass
