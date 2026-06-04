"""add fix_metadata to fix_cycles

Revision ID: 293ee95242af
Revises: e5f6a7b8c9d0
Create Date: 2026-04-09 12:02:42.502780

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "293ee95242af"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fix_cycles",
        sa.Column(
            "fix_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=True,
            comment="Runtime metadata: pid, timeout_secs, log_file, worktree_path",
        ),
    )


def downgrade() -> None:
    op.drop_column("fix_cycles", "fix_metadata")
