"""add iw core instance

Revision ID: 2bd86f8c105c
Revises: 824e6e6f34ee
Create Date: 2026-04-22 13:23:51.806402

Adds iw_core_instance — a single-row table that fingerprints the orchestration DB.
The CHECK constraint ensures only one row can ever exist (id = 1).
gen_random_uuid() is used so every deployment gets a unique instance_id.
See CR-00014.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "2bd86f8c105c"
down_revision: str | None = "824e6e6f34ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    op.create_table(
        "iw_core_instance",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column(
            "instance_id",
            sa.dialects.postgresql.UUID(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("id = 1", name="ck_iw_core_instance_single_row"),
        comment="Orchestration DB identity fingerprint — see CR-00014",
    )

    op.execute(
        "INSERT INTO iw_core_instance (id, instance_id) "
        "SELECT 1, gen_random_uuid() "
        "WHERE NOT EXISTS (SELECT 1 FROM iw_core_instance WHERE id = 1);"
    )


def downgrade() -> None:
    op.drop_table("iw_core_instance")
