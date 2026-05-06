# I-00072 S01 Backend Report

## Summary

Implemented the fix for the CLI/dashboard retry-merge parity issue (I-00072). The root cause was a local `_retryable` tuple in the CLI that only listed two of the four operator-recoverable statuses, while the dashboard had its own local copy listing three. Both now share a single `OPERATOR_RECOVERABLE_MERGE_STATUSES` constant in `orch/daemon/merge_queue.py`.

## What Was Done

### 1. New shared constant in `orch/daemon/merge_queue.py`
Added `OPERATOR_RECOVERABLE_MERGE_STATUSES` (a `frozenset`) containing all four recoverable statuses:
- `merge_failed` (CR-00028 — the missing one)
- `migration_invalid`
- `migration_rebase_failed`
- `migration_rolled_back` (I-00042 — proactive coverage)

Placed after `_CONFLICT_MARKER_RE`, before the `MergeError` class definition.

### 2. CLI wired to the constant (`orch/cli/merge_queue_commands.py`)
- Replaced the local `_retryable` tuple with `OPERATOR_RECOVERABLE_MERGE_STATUSES`
- Added the legacy back-compat path: if no new-status item is found, look for `failed` + `notes.startswith("Merge failed")`
- Added rejection of plain `failed` rows without merge notes, with the same wording as the dashboard's HTTP 422 message
- All existing behaviour preserved (worktree existence check, status flip, audit event)

### 3. Dashboard wired to the constant (`dashboard/routers/actions.py`)
- Removed local `_ALLOWED_RETRY_STATUSES`
- Now imports `OPERATOR_RECOVERABLE_MERGE_STATUSES` from `orch.daemon.merge_queue`
- Rest of `restart_merge` untouched (legacy back-compat block, batch-reopen logic, audit event)

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/merge_queue.py` | +9 lines: `OPERATOR_RECOVERABLE_MERGE_STATUSES` constant |
| `orch/cli/merge_queue_commands.py` | ~+40 lines: import constant, replace filter, add legacy path + rejection of non-merge failures |
| `dashboard/routers/actions.py` | -6 lines: removed `_ALLOWED_RETRY_STATUSES`, added import, updated reference |

## Preflight Results

| Check | Result |
|-------|--------|
| `make format` | `fixed` — ruff auto-formatted `merge_queue.py` and `merge_queue_commands.py` |
| `make typecheck` | `ok` — zero type errors in touched files |
| `make lint` | `ok` for touched files — pre-existing E501 errors in `tests/integration/test_f00055_workflow_fixture.py` are out of scope |

## Test Results

- `make test-unit TEST="tests/unit/test_merge_queue_cli.py"` — **9 passed** (existing `freeze`/`unfreeze`/`status` tests)
- `make test-unit` — 2 pre-existing failures in `tests/unit/test_safe_migrate.py` (unrelated to this change, confirmed by running against clean stash)
- `tests/unit/test_merge_queue_cli.py::test_i00072_retry_merge_accepts_merge_failed_status` will be added in **S03** (TDD — this is expected to fail on `main`, turn green after the S01 fix)

## Edge Cases Considered

1. **Empty frozenset safety**: `frozenset` is immutable — no caller can mutate the set
2. **`migration_rolled_back` forward coverage**: Added proactively even though no daemon producer exists yet — cost is zero, benefit is avoiding a future ticket
3. **Legacy back-compat scope**: The dashboard raises HTTP 422 with `detail=f"No merge-failed batch item found for {item_id}"`; the CLI error message uses the same phrasing and additionally lists the acceptable status names so operators know what changed
4. **Notes edge case**: Dashboard uses `(legacy.notes or "").startswith(...)` — CLI uses the same idiom

## Notes for S03 (Tests)

- The reproduction test `test_i00072_retry_merge_accepts_merge_failed_status` should now pass
- Need to also test: `migration_invalid`, `migration_rebase_failed`, `migration_rolled_back`, legacy `failed`+merge-notes (accept), and plain `failed` (reject with correct message)
- The parity assertion that both CLI and dashboard import the same constant covers the divergence risk going forward

## Blockers

None.