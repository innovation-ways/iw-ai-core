"""CR-00024: add warned_50pct_at to step_runs

Revision ID: cr00024warned50
Revises: cr00023workflow
Create Date: 2026-04-27 20:10:00.000000

Adds a one-time idempotency marker stamped by the step_monitor when a
50%-of-timeout soft-warn fires. NULL for all existing rows; runs that have
already crossed 50% at deploy time simply miss the one-time warn (no harm —
they were already running without warns under the pre-CR-00024 behavior).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cr00024warned50"
down_revision: str | Sequence[str] | None = "cr00023workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "step_runs",
        sa.Column(
            "warned_50pct_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment=(
                "Set by step_monitor when a one-time 50%-of-timeout warning fires "
                "for this run; suppresses duplicate warns across poll cycles (CR-00024)."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("step_runs", "warned_50pct_at")
