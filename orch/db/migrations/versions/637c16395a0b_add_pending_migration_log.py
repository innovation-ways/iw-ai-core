"""add pending migration log

Revision ID: 637c16395a0b
Revises: 2bd86f8c105c
Create Date: 2026-04-22 14:00:00.000000

Adds pending_migration_log — audit log table for daemon-driven 3-phase
migration pipeline (dry_run, apply, rollback). Records every phase the
daemon performs. Append-only. AC9 from CR-00017.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "637c16395a0b"
down_revision: str | None = "2bd86f8c105c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pending_migration_log",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("revision", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("stdout_tail", sa.Text(), nullable=True),
        sa.Column("stderr_tail", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "direction IN ('upgrade', 'downgrade')",
            name="ck_pending_migration_log_direction",
        ),
        sa.CheckConstraint(
            "phase IN ('dry_run', 'apply', 'rollback')",
            name="ck_pending_migration_log_phase",
        ),
        comment="CR-00017 audit log for daemon-driven migration phases",
    )

    op.execute(
        "CREATE SEQUENCE pending_migration_log_id_seq "
        "START WITH 1 OWNED BY pending_migration_log.id"
    )
    op.execute(
        "ALTER TABLE pending_migration_log "
        "ALTER COLUMN id SET DEFAULT nextval('pending_migration_log_id_seq')"
    )

    op.create_index(
        "ix_pending_migration_log_batch",
        "pending_migration_log",
        ["batch_id", sa.text("started_at DESC")],
    )
    op.create_index(
        "ix_pending_migration_log_revision",
        "pending_migration_log",
        ["revision", "phase"],
    )


def downgrade() -> None:
    op.drop_index("ix_pending_migration_log_revision", table_name="pending_migration_log")
    op.drop_index("ix_pending_migration_log_batch", table_name="pending_migration_log")
    op.execute("DROP SEQUENCE IF EXISTS pending_migration_log_id_seq CASCADE")
    op.drop_table("pending_migration_log")
