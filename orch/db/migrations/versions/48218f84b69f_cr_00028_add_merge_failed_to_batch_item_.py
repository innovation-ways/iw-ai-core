"""CR-00028 add merge_failed to batch_item_status enum

Revision ID: 48218f84b69f
Revises: 561ddde7f5fb
Create Date: 2026-05-02 14:27:34.741118

"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "48218f84b69f"
down_revision: str | None = "561ddde7f5fb"
branch_labels: list[str] | None = None
depends_on: list[str] | None = None


def upgrade() -> None:
    # Add the new 'merge_failed' value to the batch_item_status enum.
    # IF NOT EXISTS guards against double-application in crash-recovery replay.
    op.execute("ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'merge_failed'")


def downgrade() -> None:
    # PostgreSQL does not natively support removing values from an enum type.
    # Acceptable because the change is additive: rolling back leaves the value
    # in the type but the application no longer writes it. Operators rolling
    # back in the presence of in-flight 'merge_failed' rows must run a manual
    # SQL update first (see CR-00028 design doc Rollback Plan):
    #   UPDATE batch_items
    #      SET status = 'failed',
    #          notes = notes || ' (was merge_failed pre-rollback)'
    #    WHERE status = 'merge_failed';
    pass
