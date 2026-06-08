"""set minimax M3 context window to 1M tokens

MiniMax M3 ships a 1,000,000-token context window, up from M2.7's 204,800
(stored as 200,000 in agent_runtime_options). This migration raises
``context_window_tokens`` to 1,000,000 for the two M3 runtime rows that
opencode/pi resolve against:

  - row id=1 (cli_tool='opencode')
  - row id=7 (cli_tool='pi', the is_default runtime)

Follows 08850d673ff6 (the M2.7→M3 model rename). ``max_output_tokens`` is left
untouched (pi: 131,072). The WHERE clause is keyed on the M3 model string and
the old window value, so the migration is idempotent and a no-op if already
applied.

Applied off-band (operator → ``make db-migrate``), so ``down_revision`` is
pinned to the real chain head ``08850d673ff6`` instead of the ``PENDING``
placeholder.

Revision ID: 53e45cb21742
Revises: 08850d673ff6
Create Date: 2026-06-08 14:53:29.661196

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "53e45cb21742"
down_revision: str | tuple[str, ...] | None = "08850d673ff6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE agent_runtime_options
           SET context_window_tokens = 1000000
         WHERE model = 'minimax/MiniMax-M3'
           AND cli_tool IN ('opencode', 'pi')
           AND context_window_tokens = 200000
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE agent_runtime_options
           SET context_window_tokens = 200000
         WHERE model = 'minimax/MiniMax-M3'
           AND cli_tool IN ('opencode', 'pi')
           AND context_window_tokens = 1000000
        """
    )
