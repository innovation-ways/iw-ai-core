"""merge_f00074_keepalive_and_cm_public_id

Revision ID: efd271775dc7
Revises: 4d9ec0083240, 66366e97079b
Create Date: 2026-04-30 21:02:52.937045

"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "efd271775dc7"
down_revision: str | Sequence[str] | None = ("4d9ec0083240", "66366e97079b")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
