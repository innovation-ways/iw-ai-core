"""fix_runtime_option_model_format

opencode 1.14.x requires --model to be in `provider/model_id` format. The
F-00081 catalogue seed stored bare provider strings (e.g. "minimax") which
caused opencode to crash with `ProviderModelNotFoundError: minimax/`.

This migration:
  - Rewrites row 1 (default opencode runtime) to use `minimax/MiniMax-M2.7`.
  - Disables rows 2 and 3 — opencode does not currently have an `anthropic`
    provider configured locally; selecting them would also crash. They can
    be re-enabled by an operator after configuring the provider.

Revision ID: a1b2c3fixmm
Revises: mergef81cr00036
Create Date: 2026-05-09 22:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a1b2c3fixmm"
down_revision: str | None = "mergef81cr00036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE agent_runtime_options
           SET model = 'minimax/MiniMax-M2.7'
         WHERE id = 1
           AND cli_tool = 'opencode'
           AND model = 'minimax'
        """
    )
    op.execute(
        """
        UPDATE agent_runtime_options
           SET enabled = false
         WHERE id IN (2, 3)
           AND cli_tool = 'opencode'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE agent_runtime_options
           SET enabled = true
         WHERE id IN (2, 3)
           AND cli_tool = 'opencode'
        """
    )
    op.execute(
        """
        UPDATE agent_runtime_options
           SET model = 'minimax'
         WHERE id = 1
           AND cli_tool = 'opencode'
           AND model = 'minimax/MiniMax-M2.7'
        """
    )
