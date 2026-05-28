"""f_00091_backfill_pi_context_window_tokens

Data-only backfill for Pi runtime context windows (F-00091 / S04).

`projects.toml` currently uses `[projects.<id>.ai_assistant].models` (not
`allowed_models`) and exposes these Pi-reachable model IDs for `iw-ai-core`:
- anthropic/claude-opus-4-7
- anthropic/claude-sonnet-4-6
- minimax/MiniMax-M2.7
- openai/gpt-5.3-codex
- ollama/gemma4:26b

Only models with publishable canonical context-window sizes are backfilled here:
- (pi, anthropic/claude-opus-4-7) -> 200_000
  Source: Anthropic model docs (Claude 4 family, 200K context window):
  https://docs.anthropic.com/en/docs/about-claude/models
- (pi, anthropic/claude-sonnet-4-6) -> 200_000
  Source: Anthropic model docs (Claude 4 family, 200K context window):
  https://docs.anthropic.com/en/docs/about-claude/models
- (pi, minimax/MiniMax-M2.7) -> 200_000
  Source: MiniMax model/API docs listing a 200K context window for M2.7:
  https://www.minimax.io/platform

`openai/gpt-5.3-codex` and `ollama/gemma4:26b` are intentionally excluded from
this migration because a canonical citable context window was not pinned in
this step; they remain NULL and surface `unknown_window` in the UI.

Revision ID: 76250ecb2593
Revises: d43ea9e75e8f
Create Date: 2026-05-27 22:22:09.441173

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "76250ecb2593"
down_revision: str | tuple[str, ...] | None = "d43ea9e75e8f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PAIRS: list[tuple[str, str, int]] = [
    ("pi", "anthropic/claude-opus-4-7", 200_000),
    ("pi", "anthropic/claude-sonnet-4-6", 200_000),
    ("pi", "minimax/MiniMax-M2.7", 200_000),
]


def upgrade() -> None:
    bind = op.get_bind()
    for cli_tool, model, window in _PAIRS:
        bind.execute(
            sa.text(
                """
                UPDATE agent_runtime_options
                   SET context_window_tokens = :window
                 WHERE cli_tool = :cli_tool
                   AND model    = :model
                   AND context_window_tokens IS NULL
                """
            ),
            {"cli_tool": cli_tool, "model": model, "window": window},
        )


def downgrade() -> None:
    bind = op.get_bind()
    for cli_tool, model, window in _PAIRS:
        bind.execute(
            sa.text(
                """
                UPDATE agent_runtime_options
                   SET context_window_tokens = NULL
                 WHERE cli_tool = :cli_tool
                   AND model    = :model
                   AND context_window_tokens = :window
                """
            ),
            {"cli_tool": cli_tool, "model": model, "window": window},
        )
