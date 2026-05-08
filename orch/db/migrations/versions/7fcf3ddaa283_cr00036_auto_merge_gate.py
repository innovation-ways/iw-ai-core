"""CR-00036: auto_merge flag on Batch + awaiting_merge_approval gate state

Revision ID: 7fcf3ddaa283
Revises: 1713bc13a11d
Create Date: 2026-05-07 23:18:01.736315

Adds the `auto_merge` boolean column to the `batches` table and the
`awaiting_merge_approval` value to the `batch_item_status` enum.

`auto_merge` defaults to true, preserving existing behaviour (auto-merge on
success).  When false, items that finish their workflow steps successfully
park in `awaiting_merge_approval` instead of `completed`; an operator must
approve each merge via dashboard or CLI.

Downgrade is supported but heavy: PostgreSQL does not support removing enum
values, so the swap-type pattern (create new type, alter column, drop old,
rename) is used.  Pre-condition: no row may currently hold the
`awaiting_merge_approval` status.  Raise a clear error in downgrade if any
such rows exist.

Revision ID: 7fcf3ddaa283
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7fcf3ddaa283"
down_revision: str | None = "1713bc13a11d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add the new enum value BEFORE the column add so the single upgrade
    # step runs cleanly on a live DB.
    # IF NOT EXISTS guards against double-application in crash-recovery replay.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'awaiting_merge_approval'")

    op.add_column(
        "batches",
        sa.Column(
            "auto_merge",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether to auto-merge each item to main on success; false → operator must approve each merge",
        ),
    )


def downgrade() -> None:
    # Safety guard: refuse downgrade if any row currently holds the new enum.
    # Operators must promote those rows to 'completed' before downgrading.
    count_result = op.execute(  # type: ignore[func-returns-value]
        sa.text("SELECT COUNT(*) FROM batch_items WHERE status = 'awaiting_merge_approval'")
    )
    count = count_result.scalar() if count_result is not None else None
    if count and count > 0:
        status_name = "awaiting_merge_approval"
        pre_msg = "Cannot downgrade: " + str(count) + " batch_item row(s) have "
        mid_msg = "status = '" + status_name + "'. "
        post_msg = "UPDATE batch_items SET status = 'completed' "
        post_msg2 = "WHERE status = '" + status_name + "' before running this downgrade."
        raise RuntimeError(pre_msg + mid_msg + post_msg + post_msg2)

    # Swap-type pattern: create new enum without 'awaiting_merge_approval',
    # alter the column, drop old type, rename new type.
    # The server_default on batch_items.status must be dropped before altering
    # the column type, otherwise PostgreSQL tries to cast the literal 'pending'
    # and fails if the target enum doesn't exist yet.
    op.alter_column("batch_items", "status", server_default=None)
    op.execute(
        "CREATE TYPE batch_item_status_new AS ENUM "
        "('pending', 'setting_up', 'executing', 'completed', "
        "'merging', 'merged', 'failed', 'stalled', 'skipped', "
        "'merge_failed', 'migration_invalid', 'migration_rolled_back', "
        "'migration_rebase_failed', 'setup_failed')"
    )
    op.execute(
        "ALTER TABLE batch_items "
        "ALTER COLUMN status TYPE batch_item_status_new "
        "USING status::text::batch_item_status_new"
    )
    op.execute("DROP TYPE batch_item_status")
    op.execute("ALTER TYPE batch_item_status_new RENAME TO batch_item_status")
    op.alter_column(
        "batch_items",
        "status",
        server_default=sa.text("'pending'"),
    )

    op.drop_column("batches", "auto_merge")
