"""CR-00078 add batch_overlap_ignore

Revision ID: 3a3dfec7bfbd
Revises: aeb0e4106b55
Create Date: 2026-05-23 00:21:03.091904

Adds the ``batch_overlap_ignore`` audit table for per-batch, per-file overlap
ignores.  The composite primary key (project_id, batch_id, held_item_id,
blocking_item_id, file_pattern) enforces per-batch isolation — ignores recorded
in BATCH-A do not affect BATCH-B even when the same two work items conflict.

The two FKs use ON DELETE CASCADE so that deleting a batch or its held item
cleans up any associated ignore rows.

Design notes:
- ``file_pattern`` match is exact string equality with the glob emitted by
  ``scope_overlap.find_blocking_items`` — no fnmatch normalisation is
  applied at the DB layer.
- ``ignored_by`` is a plain TEXT placeholder; when auth lands a future CR
  replaces the single literal in the endpoint handler.
- ``reason`` is nullable and unused in the v1 UI; column exists for
  forward-compat with a future CR that adds an optional textarea.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "3a3dfec7bfbd"
down_revision: str | tuple[str, ...] | None = "aeb0e4106b55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "batch_overlap_ignore",
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("held_item_id", sa.Text(), nullable=False),
        sa.Column("blocking_item_id", sa.Text(), nullable=False),
        sa.Column("file_pattern", sa.Text(), nullable=False),
        sa.Column(
            "ignored_by",
            sa.Text(),
            nullable=False,
            comment="Operator identifier; placeholder 'operator' until auth lands",
        ),
        sa.Column(
            "ignored_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
            comment="Optional operator-supplied reason; forward-compat for future CR",
        ),
        # FK to batches(project_id, id) — cascading delete of ignore rows
        # when the batch is cancelled/archived.
        sa.ForeignKeyConstraint(
            ["project_id", "batch_id"],
            ["batches.project_id", "batches.id"],
            ondelete="CASCADE",
        ),
        # FK to batch_items(project_id, batch_id, work_item_id) — cascading
        # delete when the held item row is removed from the batch.
        sa.ForeignKeyConstraint(
            ["project_id", "batch_id", "held_item_id"],
            ["batch_items.project_id", "batch_items.batch_id", "batch_items.work_item_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "project_id",
            "batch_id",
            "held_item_id",
            "blocking_item_id",
            "file_pattern",
        ),
        comment=(
            "Per-batch audit log of operator-ignored file-level overlap pairs "
            "(CR-00078). Composite PK enforces per-batch isolation. "
            "file_pattern match uses exact string equality with the glob emitted "
            "by scope_overlap.find_blocking_items — no fnmatch normalisation."
        ),
    )


def downgrade() -> None:
    op.drop_table("batch_overlap_ignore")
