"""add_gpt_5_3_codex_runtime_option

Adds OpenCode + GPT-5.3 Codex (``openai/gpt-5.3-codex``) to the
``agent_runtime_options`` catalogue as a non-default, enabled row.

Prerequisite for the operator (not enforced by this migration):
    opencode must be authenticated for the OpenAI provider — either via
    ``opencode auth login`` (ChatGPT/Codex OAuth) or by providing an
    OpenAI API key. The model id ``openai/gpt-5.3-codex`` is the string
    opencode reports via ``opencode models`` when authenticated; bare or
    mis-prefixed strings crash opencode with ``ProviderModelNotFoundError``
    (see ``a1b2c3fixmm`` for the prior MiniMax bare-string fix).

The row is created with ``enabled=true`` so it surfaces in the dashboard
runtime-override picker (`dashboard/routers/runtime_overrides.py` filters
on ``enabled.is_(True)`` ordered by ``sort_order, id``). ``sort_order=15``
places it directly after the MiniMax 2.7 default (sort 10) and before
the legacy opencode + Anthropic rows (sort 20/30, currently disabled).

The MiniMax 2.7 default is left untouched.

Revision ID: d1e2f3gpt53c
Revises: 7ef0b420c58f
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d1e2f3gpt53c"
down_revision: str | None = "7ef0b420c58f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # F-00081 seeded rows 1-5 with explicit ids via ``bulk_insert`` but did not
    # bump the SERIAL sequence, so a plain autoincrement INSERT here collides
    # on ``agent_runtime_options_pkey`` ("duplicate key value … (id)=(1)").
    # Align the sequence to the current MAX(id) before inserting; harmless if
    # the sequence is already ahead (``is_called=true`` keeps it monotonic).
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

    # Insert as a non-default, enabled option. ``id`` is left to autoincrement
    # so we don't collide with concurrent inserts on per-worktree DBs. The
    # (cli_tool, model) unique constraint is the stable identity used by the
    # downgrade.
    op.execute(
        """
        INSERT INTO agent_runtime_options
            (cli_tool, model, cli_label, model_label, display_name,
             is_default, enabled, sort_order)
        VALUES
            ('opencode', 'openai/gpt-5.3-codex',
             'OpenCode', 'GPT-5.3 Codex',
             'OpenCode + GPT-5.3 Codex',
             false, true, 15)
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
         WHERE cli_tool = 'opencode'
           AND model    = 'openai/gpt-5.3-codex'
        """
    )
