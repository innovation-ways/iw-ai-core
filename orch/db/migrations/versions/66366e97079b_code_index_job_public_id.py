"""Add public_id (CM-XXXXX) to code_index_jobs and backfill

Revision ID: 66366e97079b
Revises: add_diagram_doc_type
Create Date: 2026-04-30 00:00:00.000000

code_index_jobs previously surfaced their raw UUID in the jobs dashboard.
This migration adds a human-readable ``public_id`` column following the
project-wide ``PREFIX-NNNNN`` convention (e.g. F-00012, O-00001) so code
mapping jobs render as ``CM-00001``, ``CM-00002``, …

Steps:
1. Add nullable ``public_id`` text column.
2. Backfill existing rows ordered by triggered_at ASC, assigning CM-00001, …
3. Add UNIQUE index on ``public_id``.
4. Make the column NOT NULL.
5. Seed (or upsert) ``id_sequences['CM']`` so future inserts continue the sequence.

Downgrade drops the column and the ``CM`` row in id_sequences.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "66366e97079b"
down_revision: str | None = "add_diagram_doc_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add nullable column.
    op.add_column(
        "code_index_jobs",
        sa.Column(
            "public_id",
            sa.Text(),
            nullable=True,
            comment="Human-readable ID (CM-00001, CM-00002, ...). Allocated via id_sequences['CM'].",
        ),
    )

    # 2. Backfill: assign CM-00001..N in triggered_at-ascending order.
    op.execute(
        """
        WITH numbered AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY triggered_at ASC, id ASC) AS rn
            FROM code_index_jobs
        )
        UPDATE code_index_jobs c
        SET public_id = 'CM-' || LPAD(numbered.rn::text, 5, '0')
        FROM numbered
        WHERE c.id = numbered.id
        """
    )

    # 3. Unique index.
    op.create_index(
        "ix_code_index_jobs_public_id",
        "code_index_jobs",
        ["public_id"],
        unique=True,
    )

    # 4. NOT NULL.
    op.alter_column("code_index_jobs", "public_id", nullable=False)

    # 5. Seed id_sequences['CM'] with the next number after the backfilled max.
    op.execute(
        """
        INSERT INTO id_sequences (prefix, next_number)
        SELECT 'CM', COALESCE((SELECT COUNT(*) FROM code_index_jobs), 0) + 1
        ON CONFLICT (prefix) DO UPDATE
            SET next_number = GREATEST(
                id_sequences.next_number,
                COALESCE((SELECT COUNT(*) FROM code_index_jobs), 0) + 1
            )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM id_sequences WHERE prefix = 'CM'")
    op.drop_index("ix_code_index_jobs_public_id", table_name="code_index_jobs")
    op.drop_column("code_index_jobs", "public_id")
