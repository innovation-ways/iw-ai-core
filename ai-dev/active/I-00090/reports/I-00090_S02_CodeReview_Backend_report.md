# I-00090 S02 — Code Review: Backend Implementation

## Scope of Review

Reviewing S01 (`backend-impl`) implementation of the fix for I-00090 — adding an
active-item predicate (`WorkItem.archived_at IS NULL` AND
`WorkItem.status NOT IN (completed, cancelled)`) to `_query_failed_steps()` and
`_query_recent_completions()` in `dashboard/routers/running.py`.

## What Was Changed

`dashboard/routers/running.py` — three focused changes:

1. **Import** (`line 21`): `WorkItemStatus` added to the `orch.db.models` import
   block.

2. **`_query_failed_steps()`** (`lines 144–145`): Two new `.where()` clauses after
   the existing step-status filter:
   ```python
   .where(WorkItem.archived_at.is_(None))
   .where(WorkItem.status.notin_([WorkItemStatus.completed, WorkItemStatus.cancelled]))
   ```

3. **`_query_recent_completions()`** (`lines 210–211`): The same two predicates
   folded into the existing multi-condition `.where()` call.

No other files were touched.

## Review Checklist

### 1. Predicate Correctness ✅

| Helper | `archived_at.is_(None)` | `status.notin_([completed, cancelled])` | Enum list |
|--------|------------------------|------------------------------------------|------------|
| `_query_failed_steps()` | ✅ line 144 | ✅ line 145 | ✅ exactly `completed`, `cancelled` |
| `_query_recent_completions()` | ✅ line 210 | ✅ line 211 | ✅ exactly `completed`, `cancelled` |

- `is_(None)` (not `== None`) — correct SQLAlchemy 2.0 idiom.
- `notin_()` (not `not_in()`) — correct SQLAlchemy 2.0 method name.
- Enum list contains **exactly** `WorkItemStatus.completed` and
  `WorkItemStatus.cancelled` — no extras, no missing values. `failed` is
  correctly absent (item-level `failed` is still active per AC2 / Notes section
  of the design doc).
- `WorkItemStatus` is imported from `orch.db.models` at line 21.

### 2. Scope Adherence ✅

| Item | Status |
|------|--------|
| `_query_running_now()` | **Unchanged** — confirmed by reading lines 90–131 |
| `get_running_count()` | **Unchanged** — confirmed by reading lines 234–237 |
| `dashboard/templates/pages/system/running.html` | **Not touched** |
| No new file created | ✅ |
| No test file touched (S03 owns that) | ✅ |
| No Alembic migration created | ✅ |

No scope violations found.

### 3. Architecture & Conventions ✅

- Helper functions remain in `dashboard/routers/running.py` — consistent with
  existing project pattern. No issue.
- The existing `WorkItem` join in both helpers is reused — no duplicate joins.
- Import ordering: `__future__`, stdlib (`dataclasses`, `datetime`, `typing`),
  third-party (`fastapi`), local (`dashboard.dependencies`, `orch.db.models`) —
  correct per project convention.
- `make lint`: **All checks passed** (no new violations introduced).
- `make format-check`: **744 files already formatted** (no regressions).

### 4. Security & Performance ✅

- Both added predicates are simple equality / IN checks against the `archived_at`
  and `status` columns of `WorkItem`. These are not user-input-derived — no
  injection surface.
- Query shape is unchanged (same joins, same subquery for error message), just
  two extra WHERE clauses on the already-joined `WorkItem` table. No new N+1
  risk.

### 5. TDD RED Evidence ✅

The S01 report states the `tdd_red_evidence` field as:

> `"n/a — query-only filter; behavioural tests added in S03 (tests-impl); see S03
> report for RED evidence"`

This is the **explicit `"n/a — query-only filter; …"` form** documented in the
S02 prompt template. It is not a blank value, not an omission, and not a bare
empty string. Acceptable.

**Reasoning about eventual S03 test correctness**: The proposed assertion
`assert all(r.item_id != "CR-DEAD" for r in rows)` against a seeded `WorkItem(
status=completed)` with a failed step would fail on pre-S01 code (because no
active-item filter exists and the completed item's step appears in the result),
and would pass after S01 (because the new predicate excludes it). This is a
correct RED-first proof. S01 does not need to produce the test itself — that is
owned by S03.

### 6. Documentation

The change is small and the design doc captures the rationale. A code comment is
optional and none was added — this is acceptable, not a finding.

## Pre-Review Gate Results

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 744 files already formatted |
| `make test-unit` | ✅ 3065 passed, 4 skipped, 6 xfailed, 1 xpassed, 0 failed |

Test run: `make test-unit` completed in ~69s with **zero failures**.

## Acceptance Criteria Traceability

| AC | Status |
|----|--------|
| **AC1** — Failed table excludes inactive items | ✅ Predicate added to `_query_failed_steps()` |
| **AC2** — Active items still surface | ✅ Enum list excludes `failed`; active statuses (in_progress, paused, failed) remain |
| **AC3** — Recently Completed filtered the same way | ✅ Same predicates added to `_query_recent_completions()` |

## Findings

No CRITICAL, HIGH, or MEDIUM_FIXABLE issues found.

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00090",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "3065 passed, 4 skipped, 6 xfailed, 1 xpassed, 0 failed",
  "notes": "S01 is a clean, minimal, correct implementation. Both helpers received exactly the two specified predicates using correct SQLAlchemy 2.0 idioms. Enum list is exactly [completed, cancelled]. Scope is respected: running-now helpers and template untouched. TDD evidence is in the acceptable 'n/a' form. Lint and format gates clean. Unit test suite shows no regressions."
}
```