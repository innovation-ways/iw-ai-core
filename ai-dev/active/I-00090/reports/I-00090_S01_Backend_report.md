# I-00090 S01 — Backend Implementation Report

## What Was Done

Added the active-item predicate to both `_query_failed_steps()` and `_query_recent_completions()` in `dashboard/routers/running.py`.

The predicate is defined as:
- `WorkItem.archived_at IS NULL` AND
- `WorkItem.status NOT IN (completed, cancelled)`

This ensures that steps from archived, completed, or cancelled work items no longer appear in the "Failed / Needs Attention" or "Recently Completed" tables on `/system/running` and `/project/{id}/running`.

## Files Changed

- `dashboard/routers/running.py`
  - Added `WorkItemStatus` to the import block (line 21)
  - `_query_failed_steps()` (line 143-145): Added `.where(WorkItem.archived_at.is_(None))` and `.where(WorkItem.status.notin_([WorkItemStatus.completed, WorkItemStatus.cancelled]))` after the existing step-status filter
  - `_query_recent_completions()` (line 210-211): Added the same two predicates inside the existing `.where()` clause

## Design Decisions

- `_query_running_now()` and `get_running_count()` were intentionally left unchanged, as documented in the design (Out of Scope).
- Used SQLAlchemy 2.0 idioms: `is_(None)` not `== None`, `notin_()` not `not_in()`.
- The existing `WorkItem` join is reused — no new joins were needed.
- Template (`dashboard/templates/pages/system/running.html`) was not modified.

## Preflight Results

| Check | Result |
|-------|--------|
| `make format` | ok — 744 files already formatted |
| `make typecheck` | ok — Success: no issues found in 255 source files |
| `make lint` | ok — All checks passed |

## Test Results

No new tests were added in this step (owned by S03). Existing test `test_query_failed_steps_query_count_bounded` is skipped due to a separate bug.

## TDD Evidence

`"n/a — query-only filter; behavioural tests added in S03 (tests-impl); see S03 report for RED evidence"`

The RED-phase evidence is owned by S03 (Tests step), which will add `tests/dashboard/test_running_router_active_filter.py` with the failing first test `test_query_failed_steps_excludes_completed_item`. This is acceptable for a query-layer-only fix where the test surface lives in the next step.

## Blockers

None.