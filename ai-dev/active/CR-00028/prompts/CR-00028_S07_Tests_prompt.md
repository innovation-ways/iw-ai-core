# CR-00028_S07_Tests_prompt

**Work Item**: CR-00028 -- Don't cascade merge-time failures to dependent items
**Step**: S07
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Allowed: testcontainers spun up by pytest fixtures (they self-label and self-destruct via Ryuk), read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB. Migrations apply automatically inside testcontainer fixtures.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00028 --json`
- `ai-dev/active/CR-00028/CR-00028_CR_Design.md` — design (acceptance criteria AC1–AC7)
- All implementation reports: S01, S03, S05
- `tests/CLAUDE.md` — test conventions (testcontainers, FTS triggers, no live DB, no importlib.reload)

## Output Files

- `tests/unit/test_merge_queue_merge_failed_status.py` — new
- `tests/unit/test_batch_manager_blocking_terminal_set.py` — new
- `tests/unit/test_batch_manager_current_execution_group.py` — new (or extend existing)
- `tests/unit/test_actions_restart_merge_preconditions.py` — new
- `tests/unit/test_actions_abandon_merge.py` — new
- `tests/unit/test_merge_status_recoverable_display.py` — new
- `tests/integration/test_merge_failure_does_not_cascade.py` — new
- `tests/integration/test_abandon_merge_triggers_cascade.py` — new
- `ai-dev/active/CR-00028/reports/CR-00028_S07_Tests_report.md` — step report

## Context

You are authoring the test suite for **CR-00028**. Read the design doc — pay close attention to acceptance criteria AC1 through AC7. Read `tests/CLAUDE.md` for test patterns and the critical rules:

- Use testcontainers, never live DB (port 5433)
- After `Base.metadata.create_all()`, run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`
- Replace `psycopg2://` with `psycopg://` in testcontainer URLs
- `DaemonEvent.metadata` is `event_metadata` in Python
- No `importlib.reload(orch.config)` — use `monkeypatch.delenv()`

## Requirements

### Unit tests

#### `tests/unit/test_merge_queue_merge_failed_status.py`

Cover AC1 + AC4:

1. `test_merge_error_writes_merge_failed_not_failed` — given a BatchItem in `merging` and a `MergeError` raised by `worktree_commit.sh`, assert `_merge_item` writes `BatchItemStatus.merge_failed` (not `failed`). Mock `subprocess.run` to return a non-zero exit. Assert WorkItem reverts to `failed` (existing behavior).
2. `test_no_worktree_path_still_writes_failed` — given a BatchItem with `worktree_info = None` (or no `path` key), assert `_merge_item` writes `BatchItemStatus.failed` (NOT `merge_failed`). This branch is unrecoverable — the cascade must still fire.
3. `test_merge_conflict_event_emitted_on_merge_failed` — assert a `merge_conflict` daemon event is created (existing behavior preserved).

#### `tests/unit/test_batch_manager_blocking_terminal_set.py`

Cover the membership invariant:

1. `test_blocking_terminal_excludes_recoverable_statuses` — assert `_BLOCKING_TERMINAL_STATUSES` excludes `merged`, `merge_failed`, `migration_invalid`, `migration_rebase_failed`.
2. `test_blocking_terminal_includes_legacy_failed` — assert `failed`, `setup_failed`, `stalled`, `skipped`, `migration_rolled_back` ARE in the set (cascade still fires for these).

#### `tests/unit/test_batch_manager_current_execution_group.py`

Cover AC2:

1. `test_current_execution_group_treats_merge_failed_as_open` — given items where group 1 contains a `merge_failed` item and group 2 contains `pending` items, assert `_current_execution_group(items)` returns 1 (the `merge_failed` keeps the group open).
2. Same for `migration_invalid` and `migration_rebase_failed` — parametrize.
3. `test_current_execution_group_skips_legacy_failed` — given group 1 with a `failed` item, group 2 with `pending`, assert `_current_execution_group` returns 2 (legacy behavior preserved). The cascade-fail logic (different code path) handles the actual cascade.

#### `tests/unit/test_actions_restart_merge_preconditions.py`

Cover AC5:

1. `test_restart_merge_accepts_merge_failed` — POST `/actions/<proj>/item/<id>/restart-merge` for an item in `merge_failed` succeeds (200 / htmx fragment).
2. Parametrize for `migration_invalid` and `migration_rebase_failed`.
3. `test_restart_merge_resets_to_completed` — assert BatchItem.status becomes `completed` after the call.
4. `test_restart_merge_rejects_pending` — POST for an item in `pending` returns 422.

Use FastAPI's `TestClient` and the `tests/dashboard/` fixtures pattern (see existing dashboard tests for the in-memory testcontainer DB setup).

#### `tests/unit/test_actions_abandon_merge.py`

Cover AC6:

1. `test_abandon_merge_flips_to_failed` — given `merge_failed`, POST `/actions/<proj>/item/<id>/abandon-merge` flips to `failed`.
2. `test_abandon_merge_emits_event` — assert a `merge_abandoned` daemon_event is created with the right `entity_id` and `entity_type`.
3. `test_abandon_merge_rejects_other_statuses` — POST for an item in `merging` (or `completed`, or `pending`) returns 422.
4. `test_abandon_merge_appends_note` — original notes preserved + " [operator abandoned via abandon-merge]" appended.
5. `test_merge_abandoned_event_in_sse_allowlist` — assert `"merge_abandoned"` is in both `dashboard.routers.sse._TOAST_EVENTS` and `_TOAST_SEVERITY`. Without this assertion, a missing SSE registry entry would silently swallow the event in production with no test failure.

#### `tests/unit/test_merge_status_recoverable_display.py` (covers AC7 unit-level)

Cover the `_merge_status()` mapping in `dashboard/routers/items.py`:

1. `test_merge_status_maps_merge_failed_to_display_value` — given a BatchItem in `merge_failed`, `_merge_status(bi)` returns `"merge_failed"`.
2. Parametrize for `migration_invalid` and `migration_rebase_failed` — same display value.
3. `test_merge_status_legacy_failed_unchanged` — given `failed`, returns `"failed"` (legacy path preserved).
4. `test_merge_status_merging_unchanged` — given `merging`, returns `"in_progress"` (no regression).

### Integration tests

#### `tests/integration/test_merge_failure_does_not_cascade.py`

Cover AC2 + AC3 end-to-end:

1. Set up a Batch with two BatchItems: I1 (group=1) and I2 (group=2). I1 in `merging`, I2 in `pending`.
2. Force `worktree_commit.sh` to fail (mock at the subprocess boundary or use a deliberately-broken worktree fixture).
3. Run `merge_queue.process_merge_queue` — assert I1 ends in `merge_failed`.
4. Run `batch_manager._process_batch` — assert I2 remains `pending` (NOT cascade-failed).
5. Assert no `batch_dependency_failed` event was emitted.
6. Assert batch.status remains `executing` (not `completed_with_errors`).

Repeat the scenario with I1 in `migration_invalid` and `migration_rebase_failed` — same assertions.

#### `tests/integration/test_abandon_merge_triggers_cascade.py`

Cover AC6 end-to-end:

1. Set up the same 2-item batch with I1 in `merge_failed`, I2 in `pending`.
2. Call the `abandon-merge` endpoint via TestClient.
3. Assert I1.status = `failed`.
4. Run `batch_manager._process_batch` — assert I2 is now `failed` with the standard cascade note ("Skipped: a dependency...").
5. Assert batch.status transitions to `completed_with_errors`.

### Updated tests

Identify any existing tests under `tests/` that assert `BatchItemStatus.failed` after a scope-gate / merge failure or after `_merge_item`. Update them to expect `merge_failed`. Tag the changes in your report so the cross-step review can audit them.

Use `grep -r "BatchItemStatus.failed\|status.*=.*'failed'" tests/` to scan candidates. NOT every match needs updating — only the ones that test the merge-failure path.

## Project Conventions

Read `tests/CLAUDE.md` for:

- Testcontainer fixture pattern (PostgreSQL on a random port, Ryuk-managed)
- FTS function/trigger SQL must run after `create_all()`
- `psycopg2://` → `psycopg://` URL replacement
- Use `pytest.fixture` and `monkeypatch`, not `importlib.reload`

## TDD Requirement

This step IS the test-authoring phase. Use TDD:

1. RED: write each test against the current code; run; confirm it fails (or already passes for unit tests of new behavior added in S03)
2. GREEN: code is already written by S03 — tests should pass after you write them correctly
3. REFACTOR: simplify test setup if possible (use fixtures, parametrize)

If a test reveals a bug in S03's implementation, raise it as a blocker — DO NOT fix the implementation in this step. The fix-cycle on S03 will handle it.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck` — your test files must type-check
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

After writing all tests:

1. `make test-unit` — all unit tests (new + existing) pass
2. `make test-integration` — all integration tests (new + existing) pass
3. Do NOT report `tests_passed: true` unless both pass

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "CR-00028",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_merge_queue_merge_failed_status.py",
    "tests/unit/test_batch_manager_blocking_terminal_set.py",
    "tests/unit/test_batch_manager_current_execution_group.py",
    "tests/unit/test_actions_restart_merge_preconditions.py",
    "tests/unit/test_actions_abandon_merge.py",
    "tests/integration/test_merge_failure_does_not_cascade.py",
    "tests/integration/test_abandon_merge_triggers_cascade.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (N new)",
  "blockers": [],
  "notes": "Existing tests updated for merge_failed expectations: list them. AC coverage matrix: AC1→<test>, AC2→<test>, ..., AC7→deferred to S15 (browser)."
}
```
