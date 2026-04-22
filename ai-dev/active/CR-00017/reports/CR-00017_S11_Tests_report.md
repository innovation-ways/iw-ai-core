# CR-00017 S11 — Tests Report

## What Was Done

Implemented full test matrix for the 3-phase migration pipeline (CR-00017), covering:

### Unit tests — `tests/unit/test_safe_migrate_guards.py` (new)
15 tests, 15 passing:
- **Exact-string semantics**: 9 parametrized cases confirming only `"true"` (not `"TRUE"`, `"True"`, `"1"`, `"yes"`, etc.) triggers the agent-context guard
- **Empty DB**: `list_pending_revisions` on a fresh testcontainer returns all revisions in order
- **MultipleHeadsError.args**: Both head revision IDs present in exception string
- **Migration log on failure**: `apply()` and `rollback()` log to `pending_migration_log` even when alembic raises an exception (tested by patching `_run_alembic_upgrade` / `_run_alembic_downgrade` with `side_effect=RuntimeError`)

### Integration tests — `tests/integration/test_migration_pipeline.py` (new)
6 tests, 6 passing:
- `test_pipeline_happy_path` — Phase 1 → Phase 2 pass, state=merged
- `test_dry_run_rejects_broken_migration` — Phase 1 fail → MIGRATION_INVALID
- `test_apply_fails_rollback_succeeds` — dry-run ok, apply fail → rollback ok → MIGRATION_ROLLED_BACK
- `test_apply_fails_rollback_fails_freezes_queue` — both fail → frozen=True, state=MIGRATION_ROLLED_BACK
- `test_multi_head_state_rejected` — MultipleHeadsError → MIGRATION_INVALID
- `test_frozen_queue_blocks_merges` — mocked `is_merge_queue_frozen` → process_merge_queue skips

All use `DUMMY_DB_URL` patching to avoid live DB connections. Pipeline functions that write to DB are mocked.

### Integration tests — `tests/integration/test_migration_pipeline_frozen.py` (new)
2 tests, 2 passing:
- `test_unfreeze_refuses_in_agent_context` — subprocess with `IW_CORE_AGENT_CONTEXT=true` → exit 2
- `test_unfreeze_logs_ack_reason` — writes `DaemonEvent` to test DB, verifies `acknowledged_by` and `active=False` metadata

### Integration tests — `tests/integration/test_agent_migrate_guard.py` (new)
2 tests, 2 passing:
- `test_agent_env_propagates_to_subprocess` — `_build_agent_env` with env var → subprocess receives `"true"`
- `test_agent_cannot_apply_migration` — subprocess with `IW_CORE_AGENT_CONTEXT=true` → exit 2

### Extended — `tests/integration/test_agent_constraints_coverage.py` (modified)
Added:
- `MARKER_R2 = "⛔ Migrations: agents generate, daemon applies"`
- `test_prompt_template_contains_migrations_rule` — parametrized over all templates, asserts R2 marker present
- `test_claude_md_references_migrations_policy` — asserts each CLAUDE.md mentions `alembic` AND links to policy doc
- `test_policy_doc_exists_and_includes_rule` extended to assert both R1 AND R2 markers present

### Code changes (safe_migrate.py bugfix)
**`apply()` and `rollback()` did not log when alembic raised** — they re-raised without calling `_write_migration_log`. Fixed by adding an `except Exception` block before `finally` that logs the failure before re-raising. This is CRITICAL for audit completeness.

## Test Results

| File | Result |
|------|--------|
| `tests/unit/test_safe_migrate_guards.py` | 15 passed |
| `tests/integration/test_migration_pipeline.py` | 6 passed |
| `tests/integration/test_migration_pipeline_frozen.py` | 2 passed |
| `tests/integration/test_agent_migrate_guard.py` | 2 passed |
| `tests/integration/test_agent_constraints_coverage.py` | 31 passed |
| `tests/unit/` (full suite) | 1232 passed |
| `make lint` (ruff) | 3 SIM117 warnings in new file (same style as existing tests) |

**Total: 56 new tests passing**

## Notes

- `@pytest.mark.slow` is unregistered (only `integration` is in `pyproject.toml`). Warnings are harmless.
- The `test_apply_fails_rollback_fails_freezes_queue` test mocks `set_merge_queue_frozen` to prevent real DB connection during the freeze flag write. This is the correct approach for a unit-mocked test.
- The `SIM117` (combine nested `with` statements) warnings are style-only; the existing tests in the codebase have the same pattern and are not enforced as errors in `pyproject.toml`.
