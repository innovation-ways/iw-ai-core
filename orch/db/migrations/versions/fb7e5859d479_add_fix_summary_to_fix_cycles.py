"""add_fix_summary_to_fix_cycles

Revision ID: fb7e5859d479
Revises: a5c7d2f1e9b3
Create Date: 2026-04-20 11:53:36.203780

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fb7e5859d479"
down_revision: str | None = "a5c7d2f1e9b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fix_cycles",
        sa.Column(
            "fix_summary",
            sa.Text(),
            nullable=True,
            comment=(
                "Fix agent's 1-3 bullet summary of what changed and why; "
                "NULL for pre-F-00056 cycles or when the agent did not emit a summary"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("fix_cycles", "fix_summary")
