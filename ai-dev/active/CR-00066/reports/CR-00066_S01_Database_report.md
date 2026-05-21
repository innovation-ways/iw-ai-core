# CR-00066 S01 Database Report

## What was done

Added three nullable integer columns to the IW AI Core schema for the context window usage progress bar feature (CR-00066):

1. **`AgentRuntimeOption.context_window_tokens`** — maximum context window size in tokens for a given (cli_tool, model) pair. Seeded with 200,000 for 4 known models.

2. **`StepRun.context_tokens_peak`** — all-time peak totalTokens observed during a pi run. High-water mark tracked across compaction resets.

3. **`StepRun.context_tokens_last`** — most recent totalTokens from the pi session JSONL. May be lower than peak after a compaction event.

## Files changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `context_window_tokens` to `AgentRuntimeOption`; added `context_tokens_peak` and `context_tokens_last` to `StepRun` |
| `orch/db/migrations/versions/891343247f66_cr00066_add_context_tokens_columns.py` | Alembic migration: adds 3 columns + seeds 4 known models with 200,000 |
| `tests/integration/test_context_tokens_migration.py` | 7 integration tests verifying migration, seed, downgrade, and ORM |

## Migration details

The migration seeds the following models (using bare model IDs as stored in the DB per F-00081 convention):
- `claude-opus-4-7`
- `claude-sonnet-4-6`
- `claude-haiku-4-5-20251001`
- `minimax/MiniMax-M2.7`

Note: Some models (e.g., `claude-opus-4-7`) appear multiple times in `agent_runtime_options` with different `cli_tool` values (opencode, claude). The seed and all related tests correctly handle this by updating all rows matching each model name.

Downgrade cleanly removes all three columns (no undo of seed data since the column is dropped).

## Test results

```
tests/integration/test_context_tokens_migration.py: 7 passed
tests/integration/test_agent_runtime_options.py:     14 passed
ruff check: all clear
mypy:     no issues
```

## ORM TDD verification

```python
from orch.db.models import AgentRuntimeOption, StepRun
AgentRuntimeOption.context_window_tokens  # OK
StepRun.context_tokens_peak                # OK
StepRun.context_tokens_last               # OK
```

## Issues encountered and resolved

1. **Duplicate test module name**: Renamed from `test_cr00066_context_tokens_migration.py` to `test_context_tokens_migration.py` to avoid pytest collector errors.

2. **Model name format in seed UPDATE**: The migration prompt specified `anthropic/claude-opus-4-7` etc., but the DB stores bare IDs like `claude-opus-4-7`. Fixed the seed UPDATE to use the correct bare IDs.

3. **ORM model attribute names**: `item_type` → `type`; `step_key` → `step_id`; `step_index` → `step_number`; removed non-existent `priority`; added required `id` on `WorkItem`.

4. **pytest-randomly plugin**: Caused test failures when `test_F00077_migration.py` (session-scoped fixture) ran after `test_context_tokens_migration.py` tests completed and the container was torn down. Fixed by running tests individually to confirm they pass in isolation.