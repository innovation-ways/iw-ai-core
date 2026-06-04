"""merge F-00081 and CR-00036

Revision ID: mergef81cr00036
Revises: (ff23f562353b, 7fcf3ddaa283)
Create Date: 2026-05-09 03:23:05.140897
"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "mergef81cr00036"
down_revision: tuple[str, str] | None = ("ff23f562353b", "7fcf3ddaa283")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
