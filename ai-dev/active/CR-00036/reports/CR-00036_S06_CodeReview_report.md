# CR-00036 S06 Code Review Report

## Work Item
CR-00036 — Batch-level `auto_merge` toggle with operator-approved manual merge

## Step Reviewed
S05 (api-impl)

## What Was Reviewed
FastAPI route additions for CR-00036 in `dashboard/routers/actions.py`:
- `POST /project/{project_id}/api/item/{item_id}/approve-merge`
- `POST /project/{project_id}/api/batch/{batch_id}/auto-merge`
- `create_batch_from_selection` extension with `auto_merge` form field

## Files Changed
| File | Purpose |
|------|---------|
| `dashboard/routers/actions.py` | 3 new/extended endpoints |
| `tests/integration/test_dashboard_actions.py` | 10 new integration tests |

## Pre-Flight Lint & Format Gate

| Check | Result | Notes |
|-------|--------|-------|
| `make lint` | ✅ PASS | ruff + node checks clean |
| `make format` | ❌ FAIL | `tests/integration/test_dashboard_actions.py` line 901 had long chain over multiple lines — fixed by applying `ruff format` |
| `make typecheck` | ✅ PASS (from S05) | mypy clean on 232 source files |

## Review Checklist

### 1. Route correctness
- `approve-merge` registered at `/project/{project_id}/api/item/{item_id}/approve-merge` ✅
  - Sibling `restart-merge` is at same path pattern ✅
  - HTTP method is `POST` ✅
  - Registered via `app.include_router(actions.router)` in `dashboard/app.py:281` ✅
- `update_batch_auto_merge` registered at `/project/{project_id}/api/batch/{batch_id}/auto-merge` ✅
  - HTTP method is `POST` ✅
  - Pattern mirrors `max-parallel` route ✅
- `create_batch_from_selection` extended with `auto_merge` form field ✅

### 2. Status code semantics
- 404 on missing batch/item: `_get_batch` and `_get_item` helpers raise `HTTPException(404)` ✅
- 409 on wrong-state transition:
  - `approve-merge`: raises `HTTPException(409)` when `ValueError` from `approve_merge()` service ✅
  - `update_batch_auto_merge`: raises `HTTPException(409)` when batch status not in `(planning, approved, paused)` ✅
- 200/204 on success with `_action_response` toast ✅
- No 500 on operator errors ✅

### 3. Form parsing
- Checkbox handling: `auto_merge: str | None = Form(None)` — missing key → `None` → `False` ✅
- Conversion logic handles `"on"`, `"true"`, `"1"` as truthy; everything else (including `"off"`, `"false"`, `"0"`, absent) → `False` ✅
- No silent acceptance of arbitrary string values beyond the defined set ✅

### 4. Service delegation
- `approve-merge` delegates to `orch.services.approve_merge(db, project_id, item_id)` ✅
  - Does NOT replicate status-check or DaemonEvent emission inline ✅
  - Service handles `SELECT ... FOR UPDATE` locking, status validation, status transition, DaemonEvent emission ✅
- `update_batch_auto_merge` performs only the status precondition + assignment ✅
  - No other state manipulation ✅
- No new business logic in the router ✅

### 5. SSE / refresh wiring
- `approve-merge` uses `reload=True` in `_action_response` → full page reload via toast mechanism ✅
  - Same pattern as `restart_merge` and `abandon_merge` (existing) ✅
- `update_batch_auto_merge` uses `reload=False` (default) → partial SSE refresh via toast ✅
  - Mirrors `update_batch_max_parallel` pattern ✅
- No new SSE channels added ✅

### 6. Auth / authorization
- Both routes follow the same auth model as sibling routes (`restart-merge`, `update_batch_max_parallel`) ✅
- No new gate, no removed check ✅

### 7. Create-batch-from-selection
- `auto_merge` form field is optional and defaults to project's `auto_merge_default` ✅
- Hardcoded `auto_publish=False` left untouched (out of scope) ✅
- `Batch(...)` constructor receives the resolved `auto_merge` boolean value ✅
- Uses `load_projects_toml(load_config().projects_toml)` to resolve project default ✅
- Falls back to `True` if exception occurs during config load ✅

### 8. Tests
- Coverage matches the test list in S05's prompt ✅
- All 10 new tests pass ✅
- Integration tests use `db_session` fixture (testcontainer) ✅
- No live DB connection ✅

## Test Results

| Suite | Result | Details |
|-------|--------|---------|
| `make lint` | ✅ PASS | ruff + node checks clean |
| `make format` | ✅ PASS | after fix, 635 files formatted |
| 10 new CR-00036 tests | ✅ 10/10 PASS | All approve-merge, update_batch_auto_merge, create_batch auto_merge tests |
| `test_approve_merge_happy_path` | ✅ PASS | awaits → completed, 204 |
| `test_approve_merge_emits_daemon_event` | ✅ PASS | `merge_approved_by_operator` event emitted |
| `test_approve_merge_rejection_wrong_status_returns_409` | ✅ PASS | 409 on completed item |
| `test_update_batch_auto_merge_planning_to_on` | ✅ PASS | checkbox "on" → True |
| `test_update_batch_auto_merge_planning_to_off` | ✅ PASS | checkbox "off" → False |
| `test_update_batch_auto_merge_checkbox_only_sends_when_checked` | ✅ PASS | absent field → False (HTMX convention) |
| `test_update_batch_auto_merge_rejection_executing` | ✅ PASS | 409 when batch executing |
| `test_update_batch_auto_merge_rejection_completed` | ✅ PASS | 409 when batch completed |
| `test_create_batch_inherits_auto_merge_default` | ✅ PASS | project default False inherited |
| `test_create_batch_respects_auto_merge_override` | ✅ PASS | explicit "on" overrides project default |

## Findings

### Format Violation (Fixed during review)
- **Severity**: MEDIUM
- **File**: `tests/integration/test_dashboard_actions.py:901`
- **Issue**: `select(Batch).where(...).order_by(...)` chain was split over 3 lines; ruff requires single-line method chain
- **Fix**: Applied `ruff format` — collapsed to one line
- **Status**: ✅ Fixed — no remaining convention violations

### No Other Findings
All checklist items pass. No CRITICAL or HIGH findings.

## Verdict

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "CR-00036",
  "step_reviewed": "S05",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [
    {
      "severity": "MEDIUM",
      "file": "tests/integration/test_dashboard_actions.py",
      "line": 901,
      "description": "Format violation: select chain split over multiple lines",
      "fix": "Applied ruff format — collapsed to single line",
      "status": "fixed"
    }
  ],
  "tests_passed": true,
  "test_summary": "10/10 new CR-00036 tests pass; 33 existing tests still pass",
  "notes": "Format violation was the only issue and was fixed during review. No convention violations remain on changed files. approve-merge correctly delegates to orch.services.approve_merge (not inline logic). update_batch_auto_merge correctly implements checkbox convention (None = unchecked = False). create_batch_from_selection correctly resolves project default for absent form field."
}
```