"""F-00077 chat conversations memory

Revision ID: e53ce8e86a3c
Revises: 4876b3246ff2
Create Date: 2026-05-03 10:48:26.886726

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e53ce8e86a3c"
down_revision: str | None = "4876b3246ff2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create ENUM for chat_messages.role
    op.execute("CREATE TYPE chat_message_role AS ENUM ('user', 'assistant', 'system')")

    # Create chat_conversations
    op.create_table(
        "chat_conversations",
        sa.Column(
            "id", sa.Text(), server_default=sa.text("gen_random_uuid()::text"), nullable=False
        ),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("module_path", sa.Text(), nullable=True),
        sa.Column(
            "context_level",
            sa.Text(),
            server_default=sa.text("'architecture'"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("rolling_summary", sa.Text(), nullable=True),
        sa.Column("summary_through_message_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_chat_conversations_project_session_recent",
        "chat_conversations",
        ["project_id", "session_id", "last_active_at"],
        unique=False,
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    # Create chat_messages
    op.create_table(
        "chat_messages",
        sa.Column(
            "id", sa.Text(), server_default=sa.text("gen_random_uuid()::text"), nullable=False
        ),
        sa.Column("conversation_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "message_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_chat_messages_conversation_created",
        "chat_messages",
        ["conversation_id", "created_at"],
        unique=False,
    )

    # Create chat_summarization_jobs
    op.create_table(
        "chat_summarization_jobs",
        sa.Column(
            "id", sa.Text(), server_default=sa.text("gen_random_uuid()::text"), nullable=False
        ),
        sa.Column("conversation_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("messages_summarized", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("summary_through_message_id", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_chat_summarization_jobs_status",
        "chat_summarization_jobs",
        ["status", "triggered_at"],
        unique=False,
    )
    op.create_index(
        "uq_chat_summarization_jobs_one_in_flight",
        "chat_summarization_jobs",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_chat_summarization_jobs_one_in_flight",
        table_name="chat_summarization_jobs",
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.drop_index("idx_chat_summarization_jobs_status", table_name="chat_summarization_jobs")
    op.drop_table("chat_summarization_jobs")
    op.drop_index("idx_chat_messages_conversation_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index(
        "idx_chat_conversations_project_session_recent",
        table_name="chat_conversations",
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.drop_table("chat_conversations")
    op.execute("DROP TYPE chat_message_role")
