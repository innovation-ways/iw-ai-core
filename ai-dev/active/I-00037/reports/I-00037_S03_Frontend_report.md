# I-00037 S03 Frontend Report

## What Was Done

Wired both dashboard routers to call `compute_batch_step_progress()` from `dashboard/utils/batch_progress.py` so the two views share a single source of truth for `progress_pct`.

### Changes

**`dashboard/routers/project_dashboard.py`**
- Added `from dashboard.utils.batch_progress import compute_batch_step_progress` import
- In `_active_batches()`: added `step_progress = compute_batch_step_progress(project_id, batch_ids, db)` before the loop (called once, bulk)
- Replaced `pct = int((done / total * 100) if total > 0 else 0)` with `pct = step_progress.get(batch.id, 0)`
- `total_items` / `completed_items` remain item-based from the existing grouped `BatchItem` query — unchanged

**`dashboard/routers/batches.py`**
- Added same import
- In `_all_batches()`: added `batch_ids = [b.id for b in batches]` + `step_progress = compute_batch_step_progress(project_id, batch_ids, db)` before the loop (called once, bulk)
- Replaced the inline `WorkflowStep` loading + Python comprehension with `pct = step_progress.get(batch.id, 0)`
- `total_items` / `completed_items` remain item-based — unchanged

### Constraints respected
- Templates untouched (dashboard.html, batches.html, batches_table_rows.html)
- `BatchSummary` and `BatchRow` dataclass shapes unchanged
- Helper called once per request, outside the loop — not per batch
- `completed_items`/`total_items` remain item-based in both routers
- No test changes (S05 owns tests)

## Test Results

```
make test-unit  → 1395 passed, 19 warnings (pre-existing, unrelated)
make lint       → 1 error in executor/scope_gate.py (pre-existing, not touched in this step)
                   dashboard/routers/project_dashboard.py  → All checks passed
                   dashboard/routers/batches.py           → All checks passed
                   dashboard/utils/batch_progress.py      → All checks passed
make typecheck  → Success: no issues found in 150 source files
```

The lint error on `executor/scope_gate.py` is pre-existing and unrelated to this step. All files modified in this step pass lint and typecheck with zero issues.

## Smoke Check

Dev environment unavailable (no local DB with mid-flight batches in this worktree). S13 browser step will catch any discrepancy between project dashboard and batches page percentages.

## Notes

- The refactor reduces the Batches view payload: previously it loaded every `WorkflowStep` as ORM objects into Python memory; the helper does counting in SQL.
- The pre-existing T201 warning (print statement in `executor/scope_gate.py`) is a separate issue outside the scope of I-00037.