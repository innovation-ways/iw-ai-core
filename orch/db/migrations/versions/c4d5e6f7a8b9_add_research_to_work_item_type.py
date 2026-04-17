"""Add Research value to work_item_type enum.

Revision ID: c4d5e6f7a8b9
Revises: b9f2c7a1e8d4
Create Date: 2026-04-17 00:00:00.000000

Extends work_item_type enum with 'Research' so research work items can be
registered via `iw register --type research`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b9f2c7a1e8d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block on older
    # PostgreSQL versions. Alembic's transactional DDL handles this on PG 12+.
    op.execute("ALTER TYPE work_item_type ADD VALUE IF NOT EXISTS 'Research'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values. Downgrade is a no-op;
    # existing rows referencing 'Research' would prevent removal anyway.
    pass
