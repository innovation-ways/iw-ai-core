# CR-00028 S03 Backend Report

## Summary

Implemented the backend behavior change for **CR-00028: Don't cascade merge-time failures to dependent items**.

The core change: introduce `merge_failed` as a non-cascading terminal status (alongside the already-existing `migration_invalid` and `migration_rebase_failed`), so operator-recoverable merge failures don't destroy correctly-implemented dependent items.

## Files Changed

### `orch/daemon/merge_queue.py`
- **Line 136** (`no-worktree-path` branch): Added inline comment explaining why this branch intentionally produces `failed` (not `merge_failed`) — it's a data-integrity issue requiring cascade.
- **Line 289** (`MergeError`/`TimeoutExpired` handler): Changed `BatchItemStatus.failed` → `BatchItemStatus.merge_failed` with a CR-00028 reference comment.

### `orch/daemon/batch_manager.py`
- **Line 59** (`_BLOCKING_TERMINAL_STATUSES`): Extended exclusion set to include `merge_failed`, `migration_invalid`, `migration_rebase_failed`. Added CR-00028 comment explaining rationale.
- **Line 1368** (`_current_execution_group`): Added the three operator-recoverable statuses to the non-terminal set, with CR-00028 comment.

### `dashboard/routers/actions.py`
- **Line 116** (`_ITEM_ACTION_LABELS`): Updated `restart-merge` description to mention all three applicable statuses. Added `abandon-merge` entry (danger=True).
- **Line 909** (new `_ALLOWED_RETRY_STATUSES` constant): Defined `{merge_failed, migration_invalid, migration_rebase_failed}` for restart-merge preconditions.
- **Line 914** (`restart_merge`): Rewrote precondition to accept the three new statuses via `.in_()` check; preserved back-compat branch for legacy `failed + "Merge failed"` notes.
- **Line 1005** (new `abandon_merge` endpoint): `POST /item/{item_id}/abandon-merge` — flips any of the three recoverable statuses → `failed` (triggering cascade), appends `[operator abandoned via abandon-merge]` to notes, emits `merge_abandoned` event.

### `dashboard/routers/sse.py`
- Added `"merge_abandoned"` to `_TOAST_EVENTS`.
- Added `"merge_abandoned": "warning"` to `_TOAST_SEVERITY`.

## Tests Updated

### `tests/unit/test_batch_manager.py`
- `TestBlockingTerminalStatuses`: Changed `test_migration_invalid_is_blocking` → `test_migration_invalid_not_blocking`; changed `test_migration_rebase_failed_is_blocking` → `test_migration_rebase_failed_not_blocking`; added `test_merge_failed_not_blocking`; restored `test_stalled_is_blocking`.
- `TestCurrentExecutionGroup`: Added three new tests verifying `merge_failed`, `migration_invalid`, `migration_rebase_failed` items keep their execution group open.
- `TestExecutionGroupDependencyCheck`: Removed `migration_invalid` and `migration_rebase_failed` from the `blocking_status` parametrization (they no longer cascade).

### `tests/unit/test_merge_queue.py`
- `TestMergeItem`: Renamed `test_failed_merge_marks_item_failed` → `test_failed_merge_marks_item_merge_failed`; renamed `test_timeout_marks_item_failed` → `test_timeout_marks_item_merge_failed`; both now assert `merge_failed`.
- `TestMergeItemC4WorkItemRevert`: Updated four tests that assert batch_item status to expect `merge_failed` instead of `failed` on merge-error and timeout paths.

## Pre-flight Results

| Check | Result |
|-------|--------|
| `make format` | ok (orch/ and dashboard/ formatted; unrelated CR-00029 file reported separately) |
| `make typecheck` | ok (0 errors in 212 source files) |
| `make lint` | ok for modified files (pre-existing line-length issue in `restart_setup` unrelated to this CR) |

## Test Results

```
===== 2291 passed, 2 skipped, 5 xfailed, 1 xpassed, 48 warnings in 53.07s =====
```

All unit tests pass. No regressions.

## Notes

- The pre-existing line-length lint error in `restart_setup` (`actions.py:1170`) is outside CR-00028 scope — it existed before this change.
- The failing tests in the first run (`test_blocking_status_in_group_0_cascades_to_group_1[BatchItemStatus.migration_invalid]`, etc.) were parametrized tests that assumed the old cascade behavior. They were fixed by removing those statuses from the parametrization and updating the corresponding `_BLOCKING_TERMINAL_STATUSES` assertions.
- S07 (tests-impl) will add comprehensive integration tests covering the full cascade/non-cascade scenarios.
