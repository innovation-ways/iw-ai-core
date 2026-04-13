"""add_project_docs_tables

Revision ID: 6a5e03db855a
Revises: 8e995f56934c
Create Date: 2026-04-13 11:27:25.058980

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "6a5e03db855a"
down_revision: str | None = "8e995f56934c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- ENUMs ---
    doc_type = postgresql.ENUM(
        "module",
        "api",
        "architecture",
        "release_notes",
        "error_catalog",
        "webhook_ref",
        "user_guide",
        name="doc_type",
        create_type=False,
    )
    doc_tier = postgresql.ENUM(
        "fully_automated",
        "semi_automated",
        "human_authored",
        name="doc_tier",
        create_type=False,
    )
    editorial_category = postgresql.ENUM(
        "technical",
        "functional",
        "guide",
        "compliance",
        "marketing",
        "release",
        name="editorial_category",
        create_type=False,
    )
    doc_status = postgresql.ENUM(
        "planned",
        "draft",
        "published",
        "archived",
        name="doc_status",
        create_type=False,
    )
    job_status = postgresql.ENUM(
        "queued",
        "running",
        "completed",
        "failed",
        name="job_status",
        create_type=False,
    )

    for enum_type in [doc_type, doc_tier, editorial_category, doc_status, job_status]:
        enum_type.create(op.get_bind(), checkfirst=True)

    # --- project_docs ---
    op.create_table(
        "project_docs",
        sa.Column(
            "id",
            sa.Text(),
            nullable=False,
            comment="Composite PK: '{project_id}:{doc_id}'",
        ),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column(
            "doc_id",
            sa.Text(),
            nullable=False,
            comment="User-defined doc identifier within project",
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("doc_type", doc_type, nullable=False),
        sa.Column("tier", doc_tier, nullable=False),
        sa.Column("editorial_category", editorial_category, nullable=False),
        sa.Column(
            "status",
            doc_status,
            nullable=False,
            server_default=sa.text("'planned'"),
        ),
        sa.Column(
            "audience",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
            comment="JSONB array of audience strings",
        ),
        sa.Column(
            "source_paths",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
            comment="JSONB array of source file paths",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=True,
            comment="Tier 1: full markdown content",
        ),
        sa.Column(
            "content_search",
            postgresql.TSVECTOR(),
            nullable=True,
            comment="PostgreSQL tsvector for full-text search",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "generated_by",
            sa.Text(),
            nullable=True,
            comment="Generator identifier (e.g., 'skill:iw-doc-generator')",
        ),
        sa.Column("html_path", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "doc_id", name="uq_project_docs_project_doc"),
        comment="Project-level documentation catalog entries",
    )
    op.create_index("idx_project_docs_project_id", "project_docs", ["project_id"])
    op.create_index(
        "idx_project_docs_fts",
        "project_docs",
        ["content_search"],
        postgresql_using="gin",
    )

    # --- project_doc_versions ---
    op.create_table(
        "project_doc_versions",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "doc_id",
            sa.Text(),
            nullable=False,
            comment="FK to project_docs.id",
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="Markdown content snapshot",
        ),
        sa.Column("generated_by", sa.Text(), nullable=True),
        sa.Column(
            "trigger_reason",
            sa.Text(),
            nullable=True,
            comment="e.g., 'manual', 'batch-merge:B-00042', 'cli:iw doc-update'",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["doc_id"], ["project_docs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Immutable version snapshots of ProjectDoc content",
    )
    op.create_index("idx_project_doc_versions_doc_id", "project_doc_versions", ["doc_id"])

    # --- doc_generation_jobs ---
    op.create_table(
        "doc_generation_jobs",
        sa.Column(
            "id",
            sa.Text(),
            nullable=False,
            comment="UUID primary key",
        ),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column(
            "doc_id",
            sa.Text(),
            nullable=True,
            comment="FK to project_docs.id; job survives doc deletion",
        ),
        sa.Column(
            "status",
            job_status,
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "agent_output",
            sa.Text(),
            nullable=True,
            comment="Raw agent stdout/result",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["doc_id"], ["project_docs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="Async AI documentation generation job tracking",
    )
    op.create_index("idx_doc_generation_jobs_project_id", "doc_generation_jobs", ["project_id"])
    op.create_index("idx_doc_generation_jobs_doc_id", "doc_generation_jobs", ["doc_id"])
    op.create_index("idx_doc_generation_jobs_status", "doc_generation_jobs", ["status"])

    # --- FTS function and trigger for project_docs ---
    op.execute(
        """\
CREATE OR REPLACE FUNCTION update_project_docs_fts() RETURNS trigger AS $$
BEGIN
    NEW.content_search := to_tsvector('english', coalesce(NEW.title, '') || ' ' || coalesce(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""
    )
    op.execute(
        """\
CREATE TRIGGER trg_project_docs_fts
    BEFORE INSERT OR UPDATE OF title, content
    ON project_docs
    FOR EACH ROW
    EXECUTE FUNCTION update_project_docs_fts();
"""
    )


def downgrade() -> None:
    # Drop FTS trigger and function
    op.execute("DROP TRIGGER IF EXISTS trg_project_docs_fts ON project_docs;")
    op.execute("DROP FUNCTION IF EXISTS update_project_docs_fts();")

    # Drop indexes and tables in reverse dependency order
    op.drop_index("idx_doc_generation_jobs_status", table_name="doc_generation_jobs")
    op.drop_index("idx_doc_generation_jobs_doc_id", table_name="doc_generation_jobs")
    op.drop_index("idx_doc_generation_jobs_project_id", table_name="doc_generation_jobs")
    op.drop_table("doc_generation_jobs")

    op.drop_index("idx_project_doc_versions_doc_id", table_name="project_doc_versions")
    op.drop_table("project_doc_versions")

    op.drop_index("idx_project_docs_fts", table_name="project_docs")
    op.drop_index("idx_project_docs_project_id", table_name="project_docs")
    op.drop_table("project_docs")

    # Drop ENUM types
    for enum_name in ["job_status", "doc_status", "editorial_category", "doc_tier", "doc_type"]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name};")
