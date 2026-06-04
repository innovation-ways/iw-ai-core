from __future__ import annotations

from alembic import command as alembic_command
from alembic.config import Config
from sqlalchemy import text

REVISION_UNDER_TEST = "76250ecb2593"
PREV_REVISION = "d43ea9e75e8f"


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_backfills_null_only_and_downgrade_reverts_only_written_values(db_engine) -> None:
    cfg = _alembic_cfg(db_engine.url.render_as_string(hide_password=False))

    # RED setup: keep only parent revision so this migration is not yet applied.
    alembic_command.downgrade(cfg, PREV_REVISION)

    with db_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO agent_runtime_options
                    (cli_tool, model, cli_label, model_label, display_name,
                     is_default, enabled, sort_order, context_window_tokens)
                VALUES
                    ('pi', 'anthropic/claude-opus-4-7', 'Pi', 'Claude Opus 4.7',
                     'Pi + Claude Opus 4.7', false, true, 910, NULL),
                    ('pi', 'minimax/MiniMax-M2.7', 'Pi', 'MiniMax M2.7',
                     'Pi + MiniMax M2.7', false, true, 911, 999999)
                ON CONFLICT (cli_tool, model) DO UPDATE
                SET context_window_tokens = EXCLUDED.context_window_tokens
                """
            )
        )

    alembic_command.upgrade(cfg, "head")

    with db_engine.connect() as conn:
        filled = conn.execute(
            text(
                """
                SELECT context_window_tokens
                  FROM agent_runtime_options
                 WHERE cli_tool = 'pi'
                   AND model = 'anthropic/claude-opus-4-7'
                """
            )
        ).scalar_one()
        preserved = conn.execute(
            text(
                """
                SELECT context_window_tokens
                  FROM agent_runtime_options
                 WHERE cli_tool = 'pi'
                   AND model = 'minimax/MiniMax-M2.7'
                """
            )
        ).scalar_one()

    assert filled == 200_000
    assert preserved == 999_999

    alembic_command.downgrade(cfg, PREV_REVISION)

    with db_engine.connect() as conn:
        reverted = conn.execute(
            text(
                """
                SELECT context_window_tokens
                  FROM agent_runtime_options
                 WHERE cli_tool = 'pi'
                   AND model = 'anthropic/claude-opus-4-7'
                """
            )
        ).scalar_one()
        still_preserved = conn.execute(
            text(
                """
                SELECT context_window_tokens
                  FROM agent_runtime_options
                 WHERE cli_tool = 'pi'
                   AND model = 'minimax/MiniMax-M2.7'
                """
            )
        ).scalar_one()

    assert reverted is None
    assert still_preserved == 999_999

    # Leave DB at head for fixture hygiene.
    alembic_command.upgrade(cfg, "head")
