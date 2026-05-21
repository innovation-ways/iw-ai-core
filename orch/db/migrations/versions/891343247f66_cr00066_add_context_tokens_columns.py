"""cr00066_add_context_tokens_columns

Revision ID: 891343247f66
Revises: 8263c6b7746b
Create Date: 2026-05-21 08:29:47.533955

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "891343247f66"
down_revision: str | tuple[str, ...] | None = "8263c6b7746b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # CR-00066: Add context window columns
    op.add_column(
        "agent_runtime_options",
        sa.Column(
            "context_window_tokens",
            sa.Integer(),
            nullable=True,
            comment="Maximum context window size in tokens for this model. "
            "Used to compute the context usage percentage shown in the step table. "
            "NULL = unknown / not yet configured. (CR-00066)",
        ),
    )
    op.add_column(
        "step_runs",
        sa.Column(
            "context_tokens_peak",
            sa.Integer(),
            nullable=True,
            comment="All-time peak totalTokens observed during this run (pi runs only). "
            "Set by step_monitor each poll cycle; never decreases (tracks high-water mark "
            "even across compaction resets). NULL for non-pi runs. (CR-00066)",
        ),
    )
    op.add_column(
        "step_runs",
        sa.Column(
            "context_tokens_last",
            sa.Integer(),
            nullable=True,
            comment="Most recent totalTokens from the pi session JSONL for this run. "
            "May be lower than context_tokens_peak after a compaction event. "
            "NULL for non-pi runs. (CR-00066)",
        ),
    )

    # Seed known models with their context window sizes.
    # Uses bare model IDs as stored in agent_runtime_options (F-00081 convention).
    op.execute(
        """
        UPDATE agent_runtime_options
        SET context_window_tokens = 200000
        WHERE model IN (
            'claude-opus-4-7',
            'claude-sonnet-4-6',
            'claude-haiku-4-5-20251001',
            'minimax/MiniMax-M2.7'
        )
        """,
    )


def downgrade() -> None:
    op.drop_column("step_runs", "context_tokens_last")
    op.drop_column("step_runs", "context_tokens_peak")
    op.drop_column("agent_runtime_options", "context_window_tokens")
