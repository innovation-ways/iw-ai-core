"""add_doc_job_trigger_reason

Revision ID: add_doc_job_trigger_reason
Revises: 20260413144509_add_doc_lint_warnings
Create Date: 2026-04-13 14:47:05.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "add_doc_job_trigger_reason"
down_revision = "add_doc_lint_warnings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "doc_generation_jobs",
        sa.Column("trigger_reason", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("doc_generation_jobs", "trigger_reason")
