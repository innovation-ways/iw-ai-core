"""add_doc_lint_warnings

Revision ID: add_doc_lint_warnings
Revises: 73a7ae48b82b
Create Date: 2026-04-13 14:45:09.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "add_doc_lint_warnings"
down_revision = "73a7ae48b82b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "doc_generation_jobs",
        sa.Column("lint_warnings", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("doc_generation_jobs", "lint_warnings")
