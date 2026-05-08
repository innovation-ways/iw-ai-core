# CR-00036 S05 API Implementation Report

## Work Item
CR-00036 — Batch-level `auto_merge` toggle with operator-approved manual merge

## Step
S05 — Dashboard HTTP routes (API surface)

---

## What Was Done

### 1. `POST /project/{project_id}/api/item/{item_id}/approve-merge` (dashboard/routers/actions.py)
- New endpoint that calls `orch.services.approve_merge(db, project_id, item_id)`
- Raises `HTTPException(409, detail=str(exc))` on `ValueError` (wrong status)
- Returns `_action_response("Merge approved — item will merge on the next daemon tick.", toast_type="success", reload=True)` on success
- Added to `_ITEM_ACTION_LABELS` registry with dialog prompt

### 2. `POST /project/{project_id}/api/batch/{batch_id}/auto-merge` (dashboard/routers/actions.py)
- New endpoint with `auto_merge: str | None = Form(None)` parameter
- Handles checkbox convention: `None` (unchecked) → `False`; `"on"`, `"true"`, `"1"` → `True`
- Rejects with 409 if batch status not in `(planning, approved, paused)`
- Sets `batch.auto_merge = new_value` and commits

### 3. `create_batch_from_selection` auto_merge carry-through (dashboard/routers/actions.py)
- Added `auto_merge` form field parsing from `request.form()`
- Resolves to project's `auto_merge_default` when field absent (via `load_projects_toml(load_config().projects_toml)`)
- Passes resolved boolean to `Batch(...)` constructor

### 4. Integration Tests (tests/integration/test_dashboard_actions.py)
Added 10 new tests:
- `test_approve_merge_happy_path` — transitions awaiting_merge_approval → completed
- `test_approve_merge_emits_daemon_event` — emits merge_approved_by_operator event
- `test_approve_merge_rejection_wrong_status_returns_409` — 409 on wrong status, no mutation
- `test_update_batch_auto_merge_planning_to_on` — enable auto-merge on planning batch
- `test_update_batch_auto_merge_planning_to_off` — disable auto-merge on planning batch
- `test_update_batch_auto_merge_checkbox_only_sends_when_checked` — None treated as False
- `test_update_batch_auto_merge_rejection_executing` — 409 when batch executing
- `test_update_batch_auto_merge_rejection_completed` — 409 when batch completed
- `test_create_batch_inherits_auto_merge_default` — project default respected when form field absent
- `test_create_batch_respects_auto_merge_override` — explicit form value overrides project default

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/actions.py` | Added `approve-merge` to `_ITEM_ACTION_LABELS`; added `approve_merge` endpoint; added `update_batch_auto_merge` endpoint; modified `create_batch_from_selection` to parse and carry `auto_merge` |
| `tests/integration/test_dashboard_actions.py` | Added `BatchItem`, `BatchItemStatus` imports; updated `_make_batch` fixture to accept `auto_merge`; added 10 new tests for CR-00036 endpoints |

---

## Test Results

| Suite | Result | Details |
|-------|--------|---------|
| `make format` | ✅ Clean | ruff format applied |
| `make typecheck` | ✅ Success | No issues in 232 source files |
| `make lint` | ✅ All checks passed | ruff + node checks clean |
| `make test-unit` | ✅ 2689 passed | All unit tests including existing CR-00036 tests |
| `tests/integration/test_dashboard_actions.py` | ✅ 33 passed | All 10 new CR-00036 tests pass |
| `tests/integration/test_batch_item_approval.py` | ✅ 7 passed | S03 service tests still pass |

---

## Quality Gates

- **format**: `make format` — clean (ruff format applied where needed)
- **typecheck**: `make typecheck` — `Success: no issues found in 232 source files`
- **lint**: `make lint` — `All checks passed!`

---

## Notes / Observations

1. **Checkbox form handling**: `<input type="checkbox">` only sends the field name when checked, so `Form(None)` correctly represents "unchecked". The conversion logic handles `"on"`, `"true"`, `"1"` as truthy values.

2. **Monkeypatch approach for create-batch tests**: Since `load_projects_toml` is imported inside the function body (not at module level), the monkeypatch targets `orch.daemon.project_registry.load_projects_toml` instead of `dashboard.routers.actions.load_projects_toml`.

3. **SSE refresh wiring**: Both endpoints use `reload=True` in `_action_response`, which triggers a full page reload via the toast mechanism (same as `restart_merge` and `abandon_merge`). This is consistent with existing patterns.

4. **Error response format**: The `approve-merge` endpoint returns 409 Conflict on `ValueError`, matching the error response pattern for similar validation failures.

---

## Pre-flight Results

```json
{
  "step": "S05",
  "agent": "api-impl",
  "work_item": "CR-00036",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/routers/actions.py",
    "tests/integration/test_dashboard_actions.py"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "33 dashboard action tests passed (10 new CR-00036 tests); 7 batch_item_approval tests passed; 2689 unit tests passed",
  "blockers": [],
  "notes": "SSE refresh follows existing reload=True pattern used by restart_merge/abandon_merge. Monkeyspatch targets source module for load_projects_toml."
}
```