"""F-00062: add worktree compose stack columns and setup_failed status to batch_items

Revision ID: 550aecbbd42b
Revises: 40af3b76e1d5
Create Date: 2026-04-25 19:59:23.063004

Three additive changes for per-worktree container isolation:
1. Add 'setup_failed' to the batch_item_status PG enum (outside tx).
2. Add worktree_db_port INTEGER NULL to batch_items.
3. Add worktree_app_port INTEGER NULL to batch_items.
4. Add worktree_compose_path TEXT NULL to batch_items.

Reversibility: downgrade drops the three columns. The 'setup_failed'
enum label is left as a dormant orphan on downgrade — PostgreSQL does not
support removing enum labels. Same trade-off as CR-00019/CR-00021.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "550aecbbd42b"
down_revision: str | None = "40af3b76e1d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'setup_failed'")

    op.add_column(
        "batch_items",
        sa.Column(
            "worktree_db_port",
            sa.Integer(),
            nullable=True,
            comment="Discovered host port for the per-worktree Postgres container; "
            "NULL when the project runs in legacy mode (no iw-config/)",
        ),
    )
    op.add_column(
        "batch_items",
        sa.Column(
            "worktree_app_port",
            sa.Integer(),
            nullable=True,
            comment="Discovered host port for the per-worktree app server container; "
            "NULL when no app service is declared or in legacy mode",
        ),
    )
    op.add_column(
        "batch_items",
        sa.Column(
            "worktree_compose_path",
            sa.Text(),
            nullable=True,
            comment="Absolute filesystem path to the rendered docker-compose-<id>.yml; "
            "NULL in legacy mode. Used by the reaper and daemon-restart re-attach logic.",
        ),
    )


def downgrade() -> None:
    op.drop_column("batch_items", "worktree_compose_path")
    op.drop_column("batch_items", "worktree_app_port")
    op.drop_column("batch_items", "worktree_db_port")
