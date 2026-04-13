"""add_doc_job_agent_columns

Revision ID: 73a7ae48b82b
Revises: 6a5e03db855a
Create Date: 2026-04-13 12:53:30.041748

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "73a7ae48b82b"
down_revision = "6a5e03db855a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "doc_generation_jobs",
        sa.Column("agent_pid", sa.Integer(), nullable=True),
    )
    op.add_column(
        "doc_generation_jobs",
        sa.Column("skill_used", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "doc_generation_jobs",
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("doc_generation_jobs", "duration_seconds")
    op.drop_column("doc_generation_jobs", "skill_used")
    op.drop_column("doc_generation_jobs", "agent_pid")
