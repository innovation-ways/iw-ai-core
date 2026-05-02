"""Add self_assess to step_type enum.

Revision ID: a9861af32872
Revises: 48218f84b69f
Create Date: 2026-05-02 22:36:08.022207

Adds the self_assess step type enum value for the per-project
self-assessment workflow step (F-00078).  PostgreSQL requires
ALTER TYPE ... ADD VALUE to run outside a transaction block, so
we use get_context().autocommit_block() — matching the pattern
used by every other enum-extending migration in this project.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op

revision: str = "a9861af32872"
down_revision: str | None = "48218f84b69f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL requires autocommit mode for ALTER TYPE ... ADD VALUE.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE step_type ADD VALUE IF NOT EXISTS 'self_assess'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    pass
