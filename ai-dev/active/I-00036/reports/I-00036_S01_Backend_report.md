# I-00036 S01 Backend Report

## What was done

Fixed the batch progress bar to report **step-level** progress instead of **item-level** progress.

**Root cause**: `_all_batches()` in `dashboard/routers/batches.py` computed `progress_pct` from `BatchItem` statuses (`completed`/`merged` count / total items), which caused the progress to jump from 0% to 100% only when an entire work item finished, ignoring mid-item step progress.

**Fix**: Modified `_all_batches()` to:
1. Query `WorkflowStep` rows for all work items in the batch
2. Compute `progress_pct = done_steps / total_steps * 100` where `done_steps` counts steps with status `completed` or `skipped`
3. Keep `total_items` and `completed_items` unchanged (still item-level, drives the "Items" column)

## Files changed

| File | Change |
|------|--------|
| `dashboard/routers/batches.py` | Rewrote step-counting logic in `_all_batches()` (lines 195–246) |

## Test results

- `ruff check dashboard/routers/batches.py` — **All checks passed**
- `mypy dashboard/routers/batches.py` — **Success: no issues found**
- `tests/unit/test_batch_archiver.py` + `tests/unit/test_batch_planner.py` — **27 passed**
- `tests/integration/test_batch_archive.py` + `tests/integration/test_batch_manager.py` + `tests/integration/test_cli_batches.py` — **37 passed**

## Issues or observations

- The fix correctly handles the edge case where a batch has no items (`pct = 0`, no division by zero)
- The `completed_items` / `total_items` fields remain unchanged for the "Items" column
- `failed` and `needs_fix` step statuses do NOT count as done (per acceptance criteria)
- The design doc notes that `project_dashboard.py` also reads `batch.progress_pct` — this should be verified in S02/S03, though it uses the same `_all_batches()` function so the fix applies automatically