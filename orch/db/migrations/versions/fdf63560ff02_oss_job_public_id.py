"""Add public_id (O-XXXXX) to project_oss_job and backfill

Revision ID: fdf63560ff02
Revises: bd4ed52cad71
Create Date: 2026-04-27 23:00:00.000000

OSS jobs previously surfaced their bigserial integer id (1, 2, 3, ...) in
URLs and the dashboard. This migration adds a human-readable ``public_id``
column following the project-wide ``PREFIX-NNNNN`` convention (e.g. F-00012,
CR-00007, BATCH-00003) so OSS jobs render as ``O-00001``, ``O-00002``, …

Steps:
1. Add nullable ``public_id`` text column.
2. Backfill existing rows ordered by id ASC, assigning ``O-00001``, ``O-00002``, …
3. Add UNIQUE index on ``public_id``.
4. Make the column NOT NULL.
5. Seed (or upsert) ``id_sequences['O']`` with ``MAX(backfilled) + 1`` so future
   inserts via ``allocate_next_id(..., 'O')`` continue the sequence cleanly.

Downgrade drops the column and the ``O`` row in id_sequences.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "fdf63560ff02"
down_revision: str | None = "bd4ed52cad71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add nullable column.
    op.add_column(
        "project_oss_job",
        sa.Column(
            "public_id",
            sa.Text(),
            nullable=True,
            comment=("Human-readable ID (O-00001, O-00002, ...). Allocated via id_sequences['O']."),
        ),
    )

    # 2. Backfill: assign O-00001..N in id-ascending order.
    op.execute(
        """
        WITH numbered AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY id ASC) AS rn
            FROM project_oss_job
        )
        UPDATE project_oss_job p
        SET public_id = 'O-' || LPAD(numbered.rn::text, 5, '0')
        FROM numbered
        WHERE p.id = numbered.id
        """
    )

    # 3. Unique index.
    op.create_index(
        "ix_project_oss_job_public_id",
        "project_oss_job",
        ["public_id"],
        unique=True,
    )

    # 4. NOT NULL.
    op.alter_column("project_oss_job", "public_id", nullable=False)

    # 5. Seed id_sequences['O'] with the next number after the backfilled max.
    #    Use INSERT ... ON CONFLICT to be idempotent and handle empty table case.
    op.execute(
        """
        INSERT INTO id_sequences (prefix, next_number)
        SELECT 'O', COALESCE((SELECT COUNT(*) FROM project_oss_job), 0) + 1
        ON CONFLICT (prefix) DO UPDATE
            SET next_number = GREATEST(
                id_sequences.next_number,
                COALESCE((SELECT COUNT(*) FROM project_oss_job), 0) + 1
            )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM id_sequences WHERE prefix = 'O'")
    op.drop_index("ix_project_oss_job_public_id", table_name="project_oss_job")
    op.drop_column("project_oss_job", "public_id")
