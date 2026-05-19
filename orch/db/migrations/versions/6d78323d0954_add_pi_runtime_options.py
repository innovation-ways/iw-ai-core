"""add_pi_runtime_options

Seeds two ``(cli_tool='pi', model=...)`` rows into the
``agent_runtime_options`` catalogue and refreshes the ``cli_tool`` column
comments on ``step_runs`` and ``batches`` to enumerate the third
runtime. CR-00062 — Pi (pi.dev) as a third agent runtime peer to
``opencode`` and ``claude``.

Pattern mirrors ``d1e2f3gpt53c_add_gpt_5_3_codex_runtime_option.py``:
realigns the SERIAL sequence with ``pg_get_serial_sequence(..., true)``
before insert (F-00081 seeded rows 1-5 with explicit ids via
``bulk_insert`` without bumping the sequence; per-worktree DBs restored
from ``pg_dump`` need the same realignment), then inserts with
``ON CONFLICT ON CONSTRAINT uq_agent_runtime_options_cli_model
DO UPDATE`` for idempotency.

Both new rows are ``enabled=true`` and ``is_default=false`` so they
surface in the dashboard runtime-override picker (which filters
``enabled.is_(True)``) without disturbing the existing MiniMax 2.7
default. Sort order 25/26 places them after the
``(opencode, openai/gpt-5.3-codex)`` row (sort 15) and before the
disabled legacy rows.

Revision ID: 6d78323d0954
Revises: 21de61b41cec
Create Date: 2026-05-18 23:15:05.132285

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6d78323d0954"
down_revision: str | tuple[str, ...] | None = "21de61b41cec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_NEW_CLI_TOOL_COMMENT = "LLM CLI tool used: 'opencode', 'claude', or 'pi'"
_OLD_STEP_RUN_COMMENT = "LLM CLI tool used: 'opencode' or 'claude'"


def upgrade() -> None:
    # F-00081 seeded rows 1-5 with explicit ids via ``bulk_insert`` but did
    # not bump the SERIAL sequence, so a plain autoincrement INSERT here
    # collides on ``agent_runtime_options_pkey`` ("duplicate key value …
    # (id)=(1)"). Align the sequence to the current MAX(id) before
    # inserting; harmless if the sequence is already ahead
    # (``is_called=true`` keeps it monotonic).
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

    # Insert Pi + MiniMax 2.7 as a non-default, enabled option.
    op.execute(
        """
        INSERT INTO agent_runtime_options
            (cli_tool, model, cli_label, model_label, display_name,
             is_default, enabled, sort_order)
        VALUES
            ('pi', 'minimax/MiniMax-M2.7',
             'Pi', 'MiniMax 2.7',
             'Pi + MiniMax 2.7',
             false, true, 25)
        ON CONFLICT ON CONSTRAINT uq_agent_runtime_options_cli_model
        DO UPDATE SET
            cli_label    = EXCLUDED.cli_label,
            model_label  = EXCLUDED.model_label,
            display_name = EXCLUDED.display_name,
            enabled      = true,
            sort_order   = EXCLUDED.sort_order
        """
    )

    # Insert Pi + GPT-5.3 Codex as a non-default, enabled option.
    op.execute(
        """
        INSERT INTO agent_runtime_options
            (cli_tool, model, cli_label, model_label, display_name,
             is_default, enabled, sort_order)
        VALUES
            ('pi', 'openai/gpt-5.3-codex',
             'Pi', 'GPT-5.3 Codex',
             'Pi + GPT-5.3 Codex',
             false, true, 26)
        ON CONFLICT ON CONSTRAINT uq_agent_runtime_options_cli_model
        DO UPDATE SET
            cli_label    = EXCLUDED.cli_label,
            model_label  = EXCLUDED.model_label,
            display_name = EXCLUDED.display_name,
            enabled      = true,
            sort_order   = EXCLUDED.sort_order
        """
    )

    # Refresh column comments to enumerate the third valid cli_tool value.
    # ``Batch.cli_tool`` previously had no explicit comment; the upgrade
    # adds one. ``StepRun.cli_tool`` had the two-value enumeration and is
    # rewritten to the three-value one.
    op.alter_column(
        "step_runs",
        "cli_tool",
        existing_type=sa.Text(),
        comment=_NEW_CLI_TOOL_COMMENT,
        existing_comment=_OLD_STEP_RUN_COMMENT,
        existing_nullable=True,
    )
    op.alter_column(
        "batches",
        "cli_tool",
        existing_type=sa.Text(),
        comment=_NEW_CLI_TOOL_COMMENT,
        existing_nullable=False,
        existing_server_default=sa.text("'opencode'"),
    )


def downgrade() -> None:
    # Reverse the column-comment refresh first so that even if the
    # subsequent DELETEs fail (e.g., a work item/step has been pinned to
    # one of the Pi rows via the ON DELETE RESTRICT FK), the schema
    # rollback that did succeed is plain to see.
    op.alter_column(
        "batches",
        "cli_tool",
        existing_type=sa.Text(),
        comment=None,
        existing_nullable=False,
        existing_server_default=sa.text("'opencode'"),
    )
    op.alter_column(
        "step_runs",
        "cli_tool",
        existing_type=sa.Text(),
        comment=_OLD_STEP_RUN_COMMENT,
        existing_comment=_NEW_CLI_TOOL_COMMENT,
        existing_nullable=True,
    )

    # Per-model DELETEs (not a blanket ``cli_tool = 'pi'``) so a future
    # Pi row with a different model is not accidentally swept on
    # downgrade.
    op.execute(
        """
        DELETE FROM agent_runtime_options
         WHERE cli_tool = 'pi'
           AND model    = 'openai/gpt-5.3-codex'
        """
    )
    op.execute(
        """
        DELETE FROM agent_runtime_options
         WHERE cli_tool = 'pi'
           AND model    = 'minimax/MiniMax-M2.7'
        """
    )
