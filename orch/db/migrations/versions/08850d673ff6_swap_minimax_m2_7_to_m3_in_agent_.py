"""swap minimax M2.7 to M3 in agent_runtime_options

MiniMax evolved their coding model from M2.7 to M3
(https://www.minimax.io/models/text/m3). This migration repoints the two
runtime-option rows that opencode/pi resolve against from
``minimax/MiniMax-M2.7`` to ``minimax/MiniMax-M3``:

  - row id=1 (cli_tool='opencode')
  - row id=7 (cli_tool='pi', the is_default runtime)

The swap is a model-string rewrite only; ids, enabled/is_default flags, and
token-window columns are left untouched so existing item/step overrides that
reference these rows keep resolving. The WHERE clause is keyed on the old
model string, so the migration is idempotent and a no-op if already applied.

Applied off-band (operator → ``make db-migrate``) rather than via the daemon
merge-queue, so ``down_revision`` is pinned to the real chain head
``cd91a3e7f215`` instead of the ``PENDING`` placeholder.

Revision ID: 08850d673ff6
Revises: cd91a3e7f215
Create Date: 2026-06-08 14:04:48.025987

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "08850d673ff6"
down_revision: str | tuple[str, ...] | None = "cd91a3e7f215"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE agent_runtime_options
           SET model = 'minimax/MiniMax-M3'
         WHERE model = 'minimax/MiniMax-M2.7'
           AND cli_tool IN ('opencode', 'pi')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE agent_runtime_options
           SET model = 'minimax/MiniMax-M2.7'
         WHERE model = 'minimax/MiniMax-M3'
           AND cli_tool IN ('opencode', 'pi')
        """
    )
