"""I-00042 add migration_invalid and migration_rolled_back to batch_item_status

Revision ID: bd4ed52cad71
Revises: 09457f0ef2e6
Create Date: 2026-04-27 22:10:46.717204

Two deltas:
1. Add 'migration_invalid' to batch_item_status PG enum (outside tx).
2. Add 'migration_rolled_back' to batch_item_status PG enum (outside tx).

Reversibility: downgrade() is a no-op. PostgreSQL does not support removing
an enum label. After downgrade, 'migration_invalid' and 'migration_rolled_back'
remain in the PG enum as dormant orphans — this is harmless because no code
path emits those values post-downgrade. Same trade-off as CR-00021 and
CR-00019.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

revision: str = "bd4ed52cad71"
down_revision: str | None = "09457f0ef2e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add both missing enum labels OUTSIDE the implicit transaction.
    # PostgreSQL requires autocommit mode for ALTER TYPE ... ADD VALUE.
    # IF NOT EXISTS makes each statement idempotent.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'migration_invalid'")
        op.execute("ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'migration_rolled_back'")


def downgrade() -> None:
    # Enum label orphan.
    # PostgreSQL does not support removing an enum label. After downgrade,
    # 'migration_invalid' and 'migration_rolled_back' remain in the PG enum
    # as dormant orphans. This is harmless — no code path emits these values
    # post-downgrade. Same trade-off as CR-00019 and CR-00021.
    pass
