"""add_claude_opus_4_8_runtime_option

Adds Claude Code + Opus 4.8 (cli_tool ``claude``, model ``claude-opus-4-8``)
to the ``agent_runtime_options`` catalogue as a non-default, enabled row so it
surfaces in the dashboard work-item runtime-override picker
(`dashboard/routers/runtime_overrides.py` filters on ``enabled.is_(True)``
ordered by ``sort_order, id``).

Context: Claude Code upgraded its top Opus model from 4.7 to 4.8; the catalogue
only carried "Claude Code + Opus 4.7" (sort 50). This adds the 4.8 row at
sort 55 — directly after the 4.7 row — and leaves 4.7 in place (non-destructive;
an operator can disable it later). The Pi + MiniMax 2.7 default is left untouched.

Prerequisite for the operator (not enforced by this migration): the local
``claude`` CLI must have access to ``claude-opus-4-8`` (the model id Claude Code
expects, matching the existing ``claude-opus-4-7`` / ``claude-sonnet-4-6`` rows
which carry no provider prefix for the ``claude`` cli_tool).

Revision ID: b4c8opus48rt
Revises: ea7f8a0d065f
Create Date: 2026-06-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b4c8opus48rt"
down_revision: str | None = "ea7f8a0d065f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # F-00081 seeded rows 1-5 with explicit ids via ``bulk_insert`` without
    # bumping the SERIAL sequence; align it to MAX(id) before an autoincrement
    # INSERT to avoid a pkey collision (harmless if the sequence is ahead).
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('agent_runtime_options', 'id'),
            GREATEST(
                (SELECT COALESCE(MAX(id), 0) FROM agent_runtime_options),
                1
            ),
            true
        )
        """
    )

    # Insert as a non-default, enabled option. ``id`` autoincrements; the
    # (cli_tool, model) unique constraint is the stable identity used by the
    # downgrade. context_window_tokens mirrors the other Claude rows; the
    # ``claude`` cli_tool leaves max_output_tokens NULL.
    op.execute(
        """
        INSERT INTO agent_runtime_options
            (cli_tool, model, cli_label, model_label, display_name,
             is_default, enabled, sort_order, context_window_tokens)
        VALUES
            ('claude', 'claude-opus-4-8',
             'Claude Code', 'Opus 4.8',
             'Claude Code + Opus 4.8',
             false, true, 55, 200000)
        ON CONFLICT ON CONSTRAINT uq_agent_runtime_options_cli_model
        DO UPDATE SET
            cli_label    = EXCLUDED.cli_label,
            model_label  = EXCLUDED.model_label,
            display_name = EXCLUDED.display_name,
            enabled      = true,
            sort_order   = EXCLUDED.sort_order
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM agent_runtime_options
         WHERE cli_tool = 'claude'
           AND model    = 'claude-opus-4-8'
        """
    )
