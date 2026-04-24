# I-00036 S02 Code Review Report

## What was done

Reviewed the S01 backend fix to the batch progress bar (step-level vs item-level progress). The change in `dashboard/routers/batches.py` is correct — `_all_batches()` now computes `progress_pct` from `WorkflowStep` done/skipped counts rather than `BatchItem` completed/merged counts.

## Files reviewed

| File | Change |
|------|--------|
| `dashboard/routers/batches.py` | S01 fix — step-counting logic in `_all_batches()` |
| `dashboard/routers/project_dashboard.py` | Reviewed independently; no changes made |

## Test results

- `ruff check dashboard/routers/batches.py` — **All checks passed**
- `mypy dashboard/routers/batches.py` — **No issues found**
- `ruff check dashboard/routers/project_dashboard.py` — **All checks passed**
- `mypy dashboard/routers/project_dashboard.py` — **No issues found**

## Issues or observations

**MEDIUM (non-blocking):** `project_dashboard.py` has its own `_active_batches()` function (lines 87–147) that still computes `progress_pct` from item-level counts, not step-level. This is a pre-existing inconsistency, not introduced by the S01 fix, but noted in the design doc. The batch list page (`/project/{id}/batches`) shows step-level progress correctly, while the project dashboard home page (`/project/{id}/`) still shows item-level progress (jumps 0→100). No mandatory fixes; this should be addressed in a follow-up to align `_active_batches()` with step-level counting.

**No blocking issues found.** The S01 implementation is correct and passes all quality checks.