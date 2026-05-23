"""I-00105 add max_output_tokens to agent_runtime_options

Revision ID: 2be8dc12874f
Revises: 3a3dfec7bfbd
Create Date: 2026-05-23 11:17:30.540459

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "2be8dc12874f"
down_revision: str | tuple[str, ...] | None = "3a3dfec7bfbd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runtime_options",
        sa.Column(
            "max_output_tokens",
            sa.Integer(),
            nullable=True,
            comment=(
                "Maximum output tokens this model can generate in a single response. "
                "Used to compute the EFFECTIVE input budget (context_window - max_output - buffer). "
                "NULL = unknown / not yet configured. (I-00105)"
            ),
        ),
    )

    # Backfill known runtimes.
    # pi / minimax/MiniMax-M2.7: 204,800-token window, 131,072 max output (MiniMax-M2.7 spec).
    op.execute(
        """
        UPDATE agent_runtime_options
        SET max_output_tokens = 131072
        WHERE cli_tool = 'pi'
          AND model    = 'minimax/MiniMax-M2.7'
        """,
    )


def downgrade() -> None:
    op.drop_column("agent_runtime_options", "max_output_tokens")
