# F-00091 S04 — Database report

## What was done
- Added a new **data-only Alembic migration**:
  - `orch/db/migrations/versions/76250ecb2593_f_00091_backfill_pi_context_window_.py`
- Migration backfills `agent_runtime_options.context_window_tokens` only when NULL for:
  - `(pi, anthropic/claude-opus-4-7) -> 200000`
  - `(pi, anthropic/claude-sonnet-4-6) -> 200000`
  - `(pi, minimax/MiniMax-M2.7) -> 200000`
- Upgrade is idempotent (`WHERE context_window_tokens IS NULL`).
- Downgrade reverts only values this migration wrote (`WHERE context_window_tokens = :window`).
- Added integration test:
  - `tests/integration/test_alembic_chat_context_backfill.py`
  - Verifies NULL-only backfill, non-NULL preservation, and precise downgrade behavior.

## Files changed
- `orch/db/migrations/versions/76250ecb2593_f_00091_backfill_pi_context_window_.py`
- `tests/integration/test_alembic_chat_context_backfill.py`

## TDD
- RED evidence captured before applying the new migration logic:
  - `AssertionError: row.context_window_tokens is None (expected 200000)`
- Then GREEN after implementation:
  - `uv run pytest tests/integration/test_alembic_chat_context_backfill.py -v` → pass.

## Verification results
- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅
- `uv run pytest tests/integration/test_alembic_chat_context_backfill.py -v` ✅ (1 passed)
- `make migration-check` ✅ (3 passed)

## Notes / sources
- `projects.toml` currently uses `ai_assistant.models` (not `allowed_models`).
- Backfill includes only models with citable context-window figures in this step.
- Cited in migration docstring:
  - Anthropic Claude models docs (200K)
  - MiniMax platform/docs (200K for MiniMax-M2.7)
