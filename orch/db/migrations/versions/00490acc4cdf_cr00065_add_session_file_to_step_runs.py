"""cr00065_add_session_file_to_step_runs

Revision ID: 00490acc4cdf
Revises: e45b45f74ea0
Create Date: 2026-05-20 17:29:27.186568

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "00490acc4cdf"
down_revision: str | tuple[str, ...] | None = "e45b45f74ea0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "step_runs",
        sa.Column(
            "session_file",
            sa.Text(),
            nullable=True,
            comment=(
                "Absolute path to the pi session .jsonl file for this run. "
                "Set by step_monitor on the first poll cycle after step launch. "
                "NULL for claude/opencode runs and pre-CR-00065 rows. (CR-00065)"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("step_runs", "session_file")
