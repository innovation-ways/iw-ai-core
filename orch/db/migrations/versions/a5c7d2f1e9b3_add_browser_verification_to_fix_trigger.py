"""Add browser_verification value to fix_trigger enum.

Revision ID: a5c7d2f1e9b3
Revises: c4d5e6f7a8b9
Create Date: 2026-04-19 00:00:00.000000

Extends fix_trigger so failed browser_verification steps can open a
FixCycle and invoke the qv_browser_fix agent, instead of plain-retrying
the same browser prompt against unchanged code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

revision: str = "a5c7d2f1e9b3"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE fix_trigger ADD VALUE IF NOT EXISTS 'browser_verification'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    pass
