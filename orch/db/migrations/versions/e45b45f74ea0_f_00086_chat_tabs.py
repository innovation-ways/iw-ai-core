"""f_00086_chat_tabs

Revision ID: e45b45f74ea0
Revises: 6d78323d0954
Create Date: 2026-05-19 08:45:59.425217

Creates the ``chat_tabs`` table that backs the multi-tab AI Assistant
(F-00086). Each row represents one user-facing chat tab bound to one
OpenCode session.

Design notes:
- ``runtime`` and ``status`` are plain TEXT (no PostgreSQL ENUM); the
  allowlist is enforced in ``orch/chat/tab_service.py`` (matches CR-00062's
  ``cli_tool`` pattern, so adding the ``pi`` runtime in F-B does not need
  a migration).
- ``id`` uses ``gen_random_uuid()`` as a server default; the pgcrypto
  extension is enabled by ``2bd86f8c105c_add_iw_core_instance``.
- ``uq_chat_tabs_default_per_project`` is a partial unique index that
  guards the bootstrap_default_tab race window only — see F-00086
  Boundary row "Bootstrap called twice concurrently".

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e45b45f74ea0"
down_revision: str | tuple[str, ...] | None = "6d78323d0954"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_tabs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.Text(),
            server_default=sa.text("'New chat'"),
            nullable=False,
        ),
        sa.Column(
            "runtime",
            sa.Text(),
            server_default=sa.text("'opencode'"),
            nullable=False,
            comment="Chat runtime: 'opencode' today; 'pi' added by F-B",
        ),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("opencode_session_id", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            server_default=sa.text("'active'"),
            nullable=False,
            comment="Tab status: 'active' or 'closed' (soft-delete)",
        ),
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
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Multi-tab AI Assistant chat tabs (F-00086)",
    )
    op.create_index(
        "ix_chat_tabs_status_last_active",
        "chat_tabs",
        ["status", sa.text("last_active_at DESC")],
    )
    op.create_index(
        "ix_chat_tabs_project_status",
        "chat_tabs",
        ["project_id", "status"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_chat_tabs_default_per_project "
        "ON chat_tabs (project_id) "
        "WHERE title = 'Default' AND status = 'active'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_chat_tabs_default_per_project")
    op.drop_index("ix_chat_tabs_project_status", table_name="chat_tabs")
    op.drop_index("ix_chat_tabs_status_last_active", table_name="chat_tabs")
    op.drop_table("chat_tabs")
