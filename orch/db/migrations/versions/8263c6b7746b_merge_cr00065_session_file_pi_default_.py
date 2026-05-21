"""merge cr00065 session_file + pi default flip heads

Revision ID: 8263c6b7746b
Revises: 00490acc4cdf, 0f11be8f2147
Create Date: 2026-05-21 07:57:28.387267

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "8263c6b7746b"
down_revision: str | tuple[str, ...] | None = ("00490acc4cdf", "0f11be8f2147")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
