# CR-00017 S07 Backend Report — CLI Implementation

## What Was Done

Implemented two new operator-facing CLI command groups (`iw migrations` and `iw merge-queue`) wrapping the S03 `safe_migrate` library and S05 `migration_pipeline`:

### `iw migrations` group
- `iw migrations list-pending` — read-only, shows pending alembic revisions (exit 0)
- `iw migrations dry-run` — spins testcontainer Postgres, validates migrations safely (exit 0 on pass, 5 on fail)
- `iw migrations apply` — applies to live DB; requires `--i-am-operator` flag (exit 3 without flag, 2 if agent context, 0 on success, 5 on failure, 4 on multi-head)

### `iw merge-queue` group
- `iw merge-queue status` — shows frozen/unfrozen state + last migration log entry (exit 0)
- `iw merge-queue unfreeze` — clears frozen flag; requires `--ack "<reason>"` (exit 3 without ack, 2 if agent context, 0 on success)

### Exit codes enforced
- 0 = success
- 2 = agent-context guard (`IW_CORE_AGENT_CONTEXT=true`)
- 3 = missing operator/ack flag
- 4 = multi-head detected
- 5 = migration failure
- 1 = unknown

## Files Changed

| File | Change |
|------|--------|
| `orch/cli/migrations_commands.py` | New — 3 commands: list-pending, dry-run, apply |
| `orch/cli/merge_queue_commands.py` | New — 2 commands: status, unfreeze |
| `orch/cli/main.py` | Added imports and `cli.add_command()` for both new groups |
| `tests/unit/test_migrations_cli.py` | New — 10 tests covering exit codes and output |
| `tests/unit/test_merge_queue_cli.py` | New — 9 tests covering exit codes and JSON output |

## Test Results

- **Unit tests**: 19 tests pass (10 migrations_cli + 9 merge_queue_cli)
- **Full suite**: 1217 unit tests pass
- **Lint**: New files pass `ruff check` (pre-existing lint errors in other files are unrelated)
- **Manual verification**:
  - `uv run iw --help` shows `migrations` and `merge-queue` groups
  - `uv run iw migrations apply` exits 3 with clear error message
  - `uv run iw merge-queue status` works (DB must have S01 migration applied for full functionality)

## Notes

- `iw merge-queue status` and `unfreeze` use `set_merge_queue_frozen`/`is_merge_queue_frozen` from `migration_pipeline.py`; the `pending_migration_log` table is created by the S01 migration (CR-00017 S01)
- All DB sessions are properly closed in `finally` blocks to prevent session leaks
- `iw migrations dry-run` uses testcontainers (never touches live DB)
- The `--json` flag is supported on all commands for machine-readable output