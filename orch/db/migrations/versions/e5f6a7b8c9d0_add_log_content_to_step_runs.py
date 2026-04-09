"""Add log_content column to step_runs table.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-09 12:00:00.000000

Stores captured agent stdout/stderr so logs survive worktree cleanup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "step_runs",
        sa.Column(
            "log_content",
            sa.Text(),
            nullable=True,
            comment="Agent stdout/stderr captured on completion",
        ),
    )


def downgrade() -> None:
    op.drop_column("step_runs", "log_content")
