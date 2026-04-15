"""Add code_index_jobs table for Code Understanding feature.

Revision ID: b9f2c7a1e8d4
Revises: add_doc_instance_guides
Create Date: 2026-04-15 00:00:00.000000

Tracks code indexing jobs per project for the Code Understanding feature (F-00045).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "b9f2c7a1e8d4"
down_revision: str | None = "add_doc_instance_guides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "code_index_jobs",
        sa.Column(
            "id", sa.Text(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")
        ),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("provider", sa.Text(), nullable=False, server_default=sa.text("'local'")),
        sa.Column("llm_model", sa.Text(), nullable=True),
        sa.Column("embed_model", sa.Text(), nullable=True),
        sa.Column("index_tier", sa.Text(), nullable=True),
        sa.Column("files_discovered", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("files_indexed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("chunks_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("languages_detected", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("errors", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("doc_id", sa.Text(), nullable=True),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["doc_id"], ["project_docs.id"], ondelete="SET NULL"),
        comment="Tracks code indexing jobs for a project",
    )
    op.create_index("idx_code_index_jobs_project_id", "code_index_jobs", ["project_id"])
    op.create_index("idx_code_index_jobs_status", "code_index_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_code_index_jobs_status", table_name="code_index_jobs")
    op.drop_index("idx_code_index_jobs_project_id", table_name="code_index_jobs")
    op.drop_table("code_index_jobs")
