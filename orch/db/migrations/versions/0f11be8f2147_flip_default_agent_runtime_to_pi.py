"""flip default agent runtime to pi

Flips the ``agent_runtime_options`` catalogue default from
``(opencode, minimax/MiniMax-M2.7)`` to ``(pi, minimax/MiniMax-M2.7)``.

CR-00065 made ``pi`` a worktree-pinned peer of ``opencode``/``claude``;
this migration promotes the Pi + MiniMax 2.7 row (seeded ``enabled=true``
but ``is_default=false`` by ``6d78323d0954_add_pi_runtime_options``) to the
catalogue default. That makes the dashboard runtime-override picker
pre-select Pi and makes the resolver's catalogue fallback resolve to Pi.

Both UPDATEs run inside the migration's single transaction: the first
clears every ``is_default=true`` row, the second sets exactly one — so the
``uq_agent_runtime_options_one_default`` partial unique index is never
momentarily violated (no instant with two true rows). The migration is
idempotent: re-running converges to the same state.

Revision ID: 0f11be8f2147
Revises: e45b45f74ea0
Create Date: 2026-05-20 22:52:47.105187

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0f11be8f2147"
down_revision: str | tuple[str, ...] | None = "e45b45f74ea0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Clear the current default first so the promote UPDATE below never
    # collides with the old default on the single-default partial unique
    # index (which only permits one is_default=true row).
    op.execute("UPDATE agent_runtime_options SET is_default = false WHERE is_default = true")
    # Promote Pi + MiniMax 2.7 to the catalogue default. The row is seeded
    # enabled by 6d78323d0954, so the CHECK constraint
    # (NOT (is_default=true AND enabled=false)) is satisfied.
    op.execute(
        """
        UPDATE agent_runtime_options
           SET is_default = true
         WHERE cli_tool = 'pi'
           AND model    = 'minimax/MiniMax-M2.7'
        """
    )


def downgrade() -> None:
    # Restore the F-00081 default: OpenCode + MiniMax 2.7 (id=1, rewritten
    # to the provider/model_id form by a1b2c3fixmm).
    op.execute("UPDATE agent_runtime_options SET is_default = false WHERE is_default = true")
    op.execute(
        """
        UPDATE agent_runtime_options
           SET is_default = true
         WHERE cli_tool = 'opencode'
           AND model    = 'minimax/MiniMax-M2.7'
        """
    )
