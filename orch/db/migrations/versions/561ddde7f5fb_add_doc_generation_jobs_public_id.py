"""add_doc_generation_jobs_public_id

Revision ID: 561ddde7f5fb
Revises: efd271775dc7
Create Date: 2026-05-01 15:06:15.556671

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "561ddde7f5fb"
down_revision: str | None = "efd271775dc7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "doc_generation_jobs",
        sa.Column(
            "public_id",
            sa.Text(),
            nullable=True,
            comment="Human-readable ID (DOC-00001, DOC-00002, ...). Allocated via id_sequences['DOC'].",
        ),
    )
    op.create_index(
        "ix_doc_generation_jobs_public_id",
        "doc_generation_jobs",
        ["public_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_doc_generation_jobs_public_id", table_name="doc_generation_jobs")
    op.drop_column("doc_generation_jobs", "public_id")
