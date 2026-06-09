"""update minimax M3 runtime option display labels

Migrations 08850d673ff6 / 53e45cb21742 swapped the minimax runtime rows to M3
and a 1M context window but only touched the ``model`` column — the
human-readable ``model_label`` / ``display_name`` columns still read
"MiniMax 2.7", so the dashboard kept showing "Pi + MiniMax 2.7" for the default
runtime even though the agent already launches minimax/MiniMax-M3.

This migration repoints the labels on the two M3 rows (opencode id=1, pi id=7):

  - model_label  : "MiniMax 2.7" -> "MiniMax M3"
  - display_name : "<cli> + MiniMax 2.7" -> "<cli> + MiniMax M3"
    (REPLACE preserves the "OpenCode + " / "Pi + " prefix)

Keyed on model='minimax/MiniMax-M3' AND the old label, so it is idempotent and
a no-op if already applied. Applied off-band (operator -> make db-migrate), so
down_revision is pinned to the real chain head 53e45cb21742.

Revision ID: 65084ea7e4b4
Revises: 53e45cb21742
Create Date: 2026-06-09 10:29:09.285983

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "65084ea7e4b4"
down_revision: str | tuple[str, ...] | None = "53e45cb21742"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE agent_runtime_options
           SET model_label  = 'MiniMax M3',
               display_name = REPLACE(display_name, 'MiniMax 2.7', 'MiniMax M3')
         WHERE model = 'minimax/MiniMax-M3'
           AND model_label = 'MiniMax 2.7'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE agent_runtime_options
           SET model_label  = 'MiniMax 2.7',
               display_name = REPLACE(display_name, 'MiniMax M3', 'MiniMax 2.7')
         WHERE model = 'minimax/MiniMax-M3'
           AND model_label = 'MiniMax M3'
        """
    )
