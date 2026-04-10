"""Add archived_at column to batches table.

Revision ID: 7e8f9a0b1c2d
Revises: 6d7d3b4a3b83
Create Date: 2026-04-10 00:00:00.000000

Stores the timestamp when a batch was archived so it can be queried
without joining on daemon_events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e8f9a0b1c2d"
down_revision: str | None = "6d7d3b4a3b83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "batches",
        sa.Column(
            "archived_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Timestamp when the batch was archived",
        ),
    )


def downgrade() -> None:
    op.drop_column("batches", "archived_at")
