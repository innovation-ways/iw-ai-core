"""add_doc_broken_links

Revision ID: 20260413150000_add_doc_broken_links
Revises: 20260413144705_add_doc_job_trigger_reason
Create Date: 2026-04-13 15:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260413150000_add_doc_broken_links"
down_revision: str | None = "20260413144705_add_doc_job_trigger_reason"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_docs",
        sa.Column("broken_links", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_docs", "broken_links")
