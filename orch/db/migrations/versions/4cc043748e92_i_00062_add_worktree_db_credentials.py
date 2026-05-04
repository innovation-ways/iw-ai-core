"""Add worktree_db_host/name/user/password columns to batch_items (I-00062)

Revision ID: 4cc043748e92
Revises: 4876b3246ff2
Create Date: 2026-05-03

Four nullable TEXT columns added to batch_items for the per-worktree Postgres
connection. These allow _launch_step to inject IW_CORE_DB_* vars into agent
subprocesses without inheriting the daemon's orch DB (port 5433) credentials.

All four columns are nullable because items without ai-dev/iw-config/ (no
per-worktree compose stack) leave them NULL. The S03 _launch_step injection
raises RuntimeError if a compose-stack item is launched with incomplete creds.

Reversibility: downgrade drops the four columns in reverse order of addition.
No backfill required — existing in-flight items operate with the legacy code
path; injection only kicks in when all four columns are non-NULL.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4cc043748e92"
down_revision: str | None = "e53ce8e86a3c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "batch_items",
        sa.Column(
            "worktree_db_host",
            sa.Text(),
            nullable=True,
            comment="Hostname or IP of the per-worktree Postgres container; "
            "NULL in legacy mode or when the compose stack has not yet been started.",
        ),
    )
    op.add_column(
        "batch_items",
        sa.Column(
            "worktree_db_name",
            sa.Text(),
            nullable=True,
            comment="Database name of the per-worktree Postgres; NULL in legacy mode.",
        ),
    )
    op.add_column(
        "batch_items",
        sa.Column(
            "worktree_db_user",
            sa.Text(),
            nullable=True,
            comment="Username for the per-worktree Postgres; NULL in legacy mode.",
        ),
    )
    op.add_column(
        "batch_items",
        sa.Column(
            "worktree_db_password",
            sa.Text(),
            nullable=True,
            comment="Password for the per-worktree Postgres; NULL in legacy mode.",
        ),
    )


def downgrade() -> None:
    op.drop_column("batch_items", "worktree_db_password")
    op.drop_column("batch_items", "worktree_db_user")
    op.drop_column("batch_items", "worktree_db_name")
    op.drop_column("batch_items", "worktree_db_host")
