"""CR-00021 rebase pipeline phase

Revision ID: 40af3b76e1d5
Revises: d6b67d4ecb9f
Create Date: 2026-04-24 23:04:28.017704

Three deltas:
1. Add 'migration_rebase_failed' to batch_item_status PG enum (outside tx).
2. Relax ck_pending_migration_log_phase to allow phase='rebase' (atomic drop+recreate).
3. Add pending_migration_log.old_revision column.

Reversibility: downgrade drops the column and restores the 3-value CHECK
constraint. The 'migration_rebase_failed' enum label is left as a dormant
orphan — PostgreSQL does not support removing enum labels. This matches the
CR-00019 precedent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "40af3b76e1d5"
down_revision: str | None = "d6b67d4ecb9f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add the new PG enum value OUTSIDE the implicit transaction.
    #    PostgreSQL requires autocommit mode for ALTER TYPE ... ADD VALUE.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'migration_rebase_failed'")

    # 2. Recreate the CHECK constraint on pending_migration_log.phase atomically
    #    (drop + add within the same implicit transaction — safe because no
    #    concurrent writer emits phase='rebase' until S03/S05 deploy).
    op.drop_constraint(
        "ck_pending_migration_log_phase",
        "pending_migration_log",
        type_="check",
    )
    op.create_check_constraint(
        "ck_pending_migration_log_phase",
        "pending_migration_log",
        "phase IN ('dry_run', 'apply', 'rollback', 'rebase')",
    )

    # 3. Add the new column (nullable, no default — NULL is correct for non-rebase phases).
    op.add_column(
        "pending_migration_log",
        sa.Column(
            "old_revision",
            sa.Text(),
            nullable=True,
            comment="Previous down_revision before the rebase phase rewrote it",
        ),
    )


def downgrade() -> None:
    # 1. Drop the column.
    op.drop_column("pending_migration_log", "old_revision")

    # 2. Restore the 3-value CHECK constraint.
    op.drop_constraint(
        "ck_pending_migration_log_phase",
        "pending_migration_log",
        type_="check",
    )
    op.create_check_constraint(
        "ck_pending_migration_log_phase",
        "pending_migration_log",
        "phase IN ('dry_run', 'apply', 'rollback')",
    )

    # 3. Enum label orphan.
    #    PostgreSQL does not support removing an enum label. After downgrade,
    #    'migration_rebase_failed' remains in the PG enum as a dormant orphan.
    #    This is harmless — no code path emits this value post-downgrade.
    #    Same trade-off as CR-00019 (awaiting_review / discarded labels).
