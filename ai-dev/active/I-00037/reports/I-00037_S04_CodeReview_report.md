# I-00037 S04 Code Review Report

## Step Reviewed: S03 (Frontend)

## Verdict: PASS

## Findings

| Severity | Category | File | Line | Description |
|----------|----------|------|------|-------------|
| CRITICAL | correctness | dashboard/routers/project_dashboard.py | 140 | Old item-level `pct = int((done / total * 100) ...)` line is **absent** — correctly replaced with `pct = step_progress.get(batch.id, 0)`. |
| CRITICAL | correctness | dashboard/routers/project_dashboard.py | 135 | Helper called **once** at line 135, before the loop — not per-batch. |
| CRITICAL | correctness | dashboard/routers/batches.py | 205,220 | Helper called once at line 205; inline `WorkflowStep` loading loop **removed** — replaced with `pct = step_progress.get(batch.id, 0)`. |
| CRITICAL | correctness | dashboard/routers/batches.py | — | `.get(batch.id, 0)` used in both routers — no raw `dict[key]` that could KeyError. |
| HIGH | correctness | dashboard/routers/project_dashboard.py | 139,145,146 | `total_items`/`completed_items` derived from `BatchItem` counts (`counts.get(batch.id, (0, 0))`) — not from step_progress dict. |
| HIGH | correctness | dashboard/routers/batches.py | 217,218 | `total_items`/`completed_items` derived from item-based count — not overwritten with step counts. |
| MEDIUM_FIXABLE | code_quality | dashboard/routers/batches.py | 21 | `WorkflowStep` imported but no longer used after removing the inline step loop. Suggest removing to clean up. |
| MEDIUM_SUGGESTION | conventions | dashboard/routers/batches.py | — | No dead code or stale comments remain after the refactor. |

### Checklist Summary

| Item | Status |
|------|--------|
| `project_dashboard.py` imports helper | ✅ |
| Helper called once (not per-batch) in `project_dashboard.py` | ✅ |
| Old item-level pct formula gone from `project_dashboard.py` | ✅ |
| `batches.py` uses helper (old inline loop removed) | ✅ |
| `.get(batch.id, 0)` used in both (no KeyError path) | ✅ |
| `total_items`/`completed_items` stay item-based in both | ✅ |
| `BatchSummary`/`BatchRow` dataclass shapes unchanged | ✅ |
| No template edits | ✅ |
| `batch_progress.py` not edited in S03 (S01 owns it) | ✅ |
| `WorkflowStep` unused import in `batches.py` | ⚠️ (suggestion only) |
| `project_id` scopes both queries in both routers | ✅ |
| `batch_ids` list constructed once and reused | ✅ |
| No dead code left from refactor | ✅ |

## Behavioural Parity Check

Given the same `project_id` and batch ID:
- Both `_active_batches()` and `_all_batches()` call `compute_batch_step_progress(project_id, batch_ids, db)` with identical arguments.
- Both use `step_progress.get(batch.id, 0)` to index into the result.
- `project_id` scopes both the `BatchItem` subquery (line 125) and the helper's SQL query (`batch_progress.py:62`).
- `batch_ids` is the same list in both routers (same ordering from `Batch.created_at.desc()`).

**No code path exists where the two routers could produce different `progress_pct` for the same batch.**

## Test Results

```
make lint       → 1 error (executor/scope_gate.py T201, pre-existing, not touched in S03)
make typecheck  → Success: no issues found in 150 source files
make test-unit  → 1395 passed, 0 failed
```

All checks on files touched in S03 (`project_dashboard.py`, `batches.py`, `batch_progress.py`) are clean.

## Notes

- The `WorkflowStep` import in `batches.py` (line 21) is now unused after the inline loop removal. This is a MEDIUM_FIXABLE issue (not blocking since it doesn't affect correctness). The import is safe to leave but should be cleaned up in a future pass.
- The pre-existing T201 lint error in `executor/scope_gate.py` is outside the scope of I-00037.