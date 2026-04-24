# S01 Backend Report — I-00037

## What was done

Created `dashboard/utils/batch_progress.py` — a single source-of-truth helper that computes batch progress as a step-based percentage using one aggregated SQL query.

### Implementation details

- **Public API**: `compute_batch_step_progress(project_id, batch_ids, db) -> dict[str, int]`
- **SQL**: Single `SELECT` with `JOIN` on `(WorkflowStep.project_id = BatchItem.project_id) AND (WorkflowStep.work_item_id = BatchItem.work_item_id)`, grouped by `BatchItem.batch_id`
- **project_id scopes BOTH** `BatchItem` (via `where()`) and `WorkflowStep` (via the join condition) — prevents cross-project work_item_id collisions
- **done set** = `{StepStatus.completed, StepStatus.skipped}` only
- **Edge cases handled**:
  - Empty `batch_ids` → returns `{}` without executing the query
  - `total_steps == 0` → `progress_pct == 0` (no divide-by-zero)
  - `SUM()` of empty group returns `None` → guarded with `or 0`
  - All requested batch_ids always present in result dict (defaults to 0)
- **progress_pct formula**: `int((done / total * 100) if total > 0 else 0)` — matches existing `int(...)` style in `batches.py` and `project_dashboard.py`

### Files changed

| File | Change |
|------|--------|
| `dashboard/utils/batch_progress.py` | Created (new file) |
| `dashboard/utils/__init__.py` | Pre-existed — NOT modified |

### Pre-existing `dashboard/utils/__init__.py`

Confirmed that `dashboard/utils/__init__.py` already existed with content:
```python
"""Dashboard utility modules."""
```
No changes were made to it.

## Verification

- **`make lint`**: Only pre-existing issue in `executor/scope_gate.py:75` (`print` statement) — unrelated to this change. 0 lint errors in `dashboard/utils/batch_progress.py`.
- **`make typecheck`**: Success on all 150 source files.
- **`make test-unit`**: 1395 passed, 0 failures.
- **Sanity check**: Ran helper against live DB for project `iw-ai-core` with 3 known batches — returned correct pct values (100, 100, 26).

## Notes

- `batches.py` (lines 213-226) and `project_dashboard.py` (line 137) were NOT modified — they remain as-is; S03 will rewire them to call this helper.
- No migration generated — the helper reads existing tables `WorkflowStep`, `BatchItem`, `StepStatus` which already have the necessary columns.
- `dashboard/routers/batches.py` and `dashboard/routers/project_dashboard.py` confirmed untouched.