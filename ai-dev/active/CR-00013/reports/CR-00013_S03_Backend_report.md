# CR-00013 S03 Backend Report

**Step**: S03
**Agent**: backend-impl
**Work Item**: CR-00013 -- Dashboard navigation performance
**Completion Status**: complete

---

## What Was Done

Rewrote five N+1 query hotspots to issue bounded query counts independent of row counts (AC3).

### C1 — `_project_stats` (`dashboard/routers/projects.py:71`)

- Added `_all_project_stats(db, project_ids)` that runs 4 GROUP BY queries (one per stat type) instead of 4×N per-project queries
- `project_selector` route now calls `_all_project_stats` once for all projects, zips results into `ProjectWithStats` list
- `_project_stats` kept for backward compatibility callers
- **Before**: 4 queries × N projects. **After**: 4 queries total

### C2 — `_active_batches` (`dashboard/routers/project_dashboard.py:87`)

- Replaced N×2 per-batch `count()` queries with a single `GROUP BY batch_id` aggregation returning both `total` and `done` counts
- **Before**: 1 + 2×B queries (B = batch count). **After**: 1 + 1 query

### C3 — `_batch_item_rows` (`dashboard/routers/batches.py:114`)

- Collects all `(project_id, work_item_id)` tuples, issues one bulk `WorkItem` query with `tuple_()` IN clause
- Issues one bulk `WorkflowStep` query for all referenced work items (instead of N queries)
- Builds dict maps; loop body is pure in-memory lookups
- **Before**: 1 + 2×N queries. **After**: 1 + 2 queries

### C4 — `_get_steps` (`dashboard/routers/items.py:357`)

- Uses window functions (`row_number()` + `count()` OVER) in a subquery to get last run + run count for all steps in a single round-trip
- Creates lightweight in-memory `StepRun` objects with only `id`, `step_id`, `error_message` — sufficient for the template's needs
- All 4 call sites (items.py:840, 873, 903, 959) are automatically fixed
- **Before**: 1 + 2 + 2×S queries (S = step count). **After**: 1 + 2 + 2 queries

### C5 — `_query_failed_steps` (`dashboard/routers/running.py:97`)

- Same window-function pattern as C4 to bulk-load `StepRun` entries for all failed steps
- **Before**: 1 + 1×F queries (F = failed step count). **After**: 1 + 1 query

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/projects.py` | Added `_all_project_stats`; `project_selector` uses bulk query |
| `dashboard/routers/project_dashboard.py` | `_active_batches` uses single GROUP BY aggregation |
| `dashboard/routers/batches.py` | `_batch_item_rows` uses bulk WorkItem + WorkflowStep queries |
| `dashboard/routers/items.py` | `_get_steps` uses window-function bulk StepRun load |
| `dashboard/routers/running.py` | `_query_failed_steps` uses window-function bulk StepRun load |

---

## Test Results

| Suite | Result |
|-------|--------|
| `make test-unit` | 1264 passed, 19 warnings |
| `make test-integration` | 924 passed, 7 skipped, 34 warnings |
| `uv run ruff check` on changed files | All checks passed |
| `uv run mypy` on changed files | Success: no issues found |

---

## Blockers

None.

---

## Notes

- C4 fix required creating minimal `StepRun` objects in memory since the window function approach doesn't allow selecting the full ORM entity cleanly via `last_run_sub.c.StepRun`. Only `id`, `step_id`, and `error_message` are needed by templates, so a lightweight object suffices.
- The existing `test_I00034_get_steps_query_count_is_bounded` test (which enforces ≤17 queries for N=10 steps) passes with the new code, confirming the N+1 regression is fixed.
- All 14 integration test failures from the initial run were pre-existing bugs introduced in the first edit pass: `UnboundLocalError` on `func` (scoped import inside `if` block), `ImportError` for `select from sqlalchemy.dialects.postgresql`, and `AttributeError` for ORM entity in subquery column access. All fixed.
