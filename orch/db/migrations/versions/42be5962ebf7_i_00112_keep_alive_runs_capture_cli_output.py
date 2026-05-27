"""I-00112 keep_alive_runs capture CLI output

Revision ID: 42be5962ebf7
Revises: 2be8dc12874f
Create Date: 2026-05-27 08:48:43.066292

Adds four nullable columns to keep_alive_runs: stdout, stderr, elapsed_ms,
returncode. Existing rows survive with NULL. Downgrade drops the four
columns in reverse order (returncode → elapsed_ms → stderr → stdout).

Ref: I-00112
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "42be5962ebf7"
down_revision: str | None = "2be8dc12874f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "keep_alive_runs",
        sa.Column("stdout", sa.Text(), nullable=True),
    )
    op.add_column(
        "keep_alive_runs",
        sa.Column("stderr", sa.Text(), nullable=True),
    )
    op.add_column(
        "keep_alive_runs",
        sa.Column("elapsed_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "keep_alive_runs",
        sa.Column("returncode", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("keep_alive_runs", "returncode")
    op.drop_column("keep_alive_runs", "elapsed_ms")
    op.drop_column("keep_alive_runs", "stderr")
    op.drop_column("keep_alive_runs", "stdout")
