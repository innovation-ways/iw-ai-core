"""disable_claude_opus_4_7_runtime_options

Claude Code's Opus 4.7 model is no longer available, so it must stop being
offered. Disables every ``agent_runtime_options`` row for model
``claude-opus-4-7`` (cli_tool ``claude`` and the already-disabled ``opencode``
row) by setting ``enabled=false``.

The rows are NOT deleted: ``workflow_steps``, ``work_items`` and ``step_runs``
reference them via ``agent_runtime_option_id`` with ``ON DELETE RESTRICT``, so a
DELETE would either fail or destroy historical audit data. Disabling drops the
option from every dashboard picker (all filter ``enabled.is_(True)``) while
preserving the rows that past runs point at.

Pairs with ``b4c8opus48rt`` (which added Opus 4.8). The Pi + MiniMax 2.7 default
is untouched.

Revision ID: c7d9disable47
Revises: b4c8opus48rt
Create Date: 2026-06-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c7d9disable47"
down_revision: str | None = "b4c8opus48rt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE agent_runtime_options
           SET enabled = false
         WHERE model = 'claude-opus-4-7'
        """
    )


def downgrade() -> None:
    # Restore the pre-change state: the ``claude`` row was enabled; the
    # ``opencode`` row was already disabled, so it stays disabled.
    op.execute(
        """
        UPDATE agent_runtime_options
           SET enabled = true
         WHERE cli_tool = 'claude'
           AND model    = 'claude-opus-4-7'
        """
    )
