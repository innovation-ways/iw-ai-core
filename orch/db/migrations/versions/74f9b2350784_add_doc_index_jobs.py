"""Add doc_index_jobs table for hybrid doc Q&A feature.

Revision ID: 74f9b2350784
Revises: 1fb2eb17b580
Create Date: 2026-04-24 08:38:51.835876

Tracks doc indexing jobs per project for the hybrid Code Q&A feature (F-00060).
Structural clone of code_index_jobs with items_* renamed columns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "74f9b2350784"
down_revision: str | None = "1fb2eb17b580"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "doc_index_jobs",
        sa.Column(
            "id", sa.Text(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")
        ),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("provider", sa.Text(), nullable=False, server_default=sa.text("'local'")),
        sa.Column("llm_model", sa.Text(), nullable=True),
        sa.Column("embed_model", sa.Text(), nullable=True),
        sa.Column("index_tier", sa.Text(), nullable=True),
        sa.Column("items_discovered", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_indexed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("chunks_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("errors", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        comment="Tracks doc indexing jobs for a project",
    )
    op.create_index("idx_doc_index_jobs_project_id", "doc_index_jobs", ["project_id"])
    op.create_index("idx_doc_index_jobs_status", "doc_index_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_doc_index_jobs_status", table_name="doc_index_jobs")
    op.drop_index("idx_doc_index_jobs_project_id", table_name="doc_index_jobs")
    op.drop_table("doc_index_jobs")
