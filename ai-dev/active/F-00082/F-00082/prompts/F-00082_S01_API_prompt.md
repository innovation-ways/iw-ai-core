# F-00082_S01_API_prompt

**Work Item**: F-00082 -- Dashboard Cancel Buttons (Batch + Work Item)
**Step**: S01
**Agent**: API (`api-impl`)

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. Testcontainer fixtures spun up by pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds **no migrations**. If you find yourself needing to change schema, STOP and raise a blocker — F-00082 is wrap-only.

## Input Files

- **Runtime step state** (authoritative): `uv run iw item-status F-00082 --json`.
- `ai-dev/active/F-00082/F-00082_Feature_Design.md` — design doc (read in full).
- `ai-dev/active/F-00082/F-00082_Functional.md` — human-facing summary.
- Service layer (already merged): `orch/cancel.py` — DO NOT modify; consume only.
- Existing endpoints to rewrite: `dashboard/routers/actions.py` lines 519 (`cancel_item`), 1596 (`cancel_batch`), plus the confirm-dialog GET handlers.
- Existing modal scaffold: `dashboard/templates/components/confirm_dialog.html`, `dashboard/templates/fragments/confirm_action.html`.

## Output Files

- `ai-dev/active/F-00082/reports/F-00082_S01_API_report.md` — Step report.

## Context

You are rewriting the two cancel HTTP endpoints (item + batch) in the FastAPI dashboard so they delegate to the `orch.cancel` service layer that just shipped, and you are extending the confirm-dialog GET endpoint to deliver a **form-bearing** modal for cancel actions. The Frontend step (S03) consumes this contract — keep it stable.

Read `dashboard/CLAUDE.md` first for the routers-are-thin pattern, htmx conventions, fragment templates, and the no-direct-`navigator.clipboard` rule (not applicable here but read it).

## Requirements

### 1. Rewrite `POST /project/{project_id}/api/item/{item_id}/cancel`

Replace the body of `cancel_item` in `dashboard/routers/actions.py`:

- Accept two **optional** form fields:
  - `reason: str = Form("cancelled by operator")`
  - `to_draft: bool = Form(False)` — must accept `"true"` / `"on"` / `"1"` from a checkbox input (FastAPI's `Form(bool)` already handles these).
- Delegate to `orch.cancel.cancel_work_item(db, project_id, item_id, reason=reason, to_draft=to_draft)`.
- Map `LookupError` → `HTTPException(status_code=404, detail=str(exc))`.
- Map `ValueError` → `HTTPException(status_code=422, detail=str(exc))`. **Exception**: if the error message contains the substring `"active batch"`, use `status_code=409` (Conflict) — semantically more accurate when the resource exists but is gated by another active resource. The frontend renders both as a toast; the differentiation is for callers using the API directly.
- On success, build a human toast that:
  - Names the new status (`draft` if `to_draft`, else `cancelled`).
  - Includes the reason.
  - If `result.teardown_errors` is non-empty, appends a separate warning line per error.
- Use `_action_response(...)` with `reload=True` so the page refreshes (same shape as the existing `approve`/`unapprove` handlers).

### 2. Rewrite `POST /project/{project_id}/api/batch/{batch_id}/cancel`

Replace the body of `cancel_batch` in `dashboard/routers/actions.py`:

- Accept two **optional** form fields:
  - `reason: str = Form("cancelled by operator")`
  - `reset_items: bool = Form(False)`
- Delegate to `orch.cancel.cancel_batch(db, project_id, batch_id, reason=reason, reset_items=reset_items)`.
- Same `LookupError` → 404 / `ValueError` → 422 mapping. (No 409 carve-out here — `ValueError` from cancel_batch is always a status guard, never a cross-resource conflict.)
- On success, build a toast that lists `cancelled_batch_items`, `reset_to_draft` (if any), and `killed_pids` (if any). Append a warning line per `teardown_error`.
- Use `_action_response(..., reload=True)`.

### 3. Confirm-dialog GET handlers — form-bearing variant for cancel

The existing GET endpoints `/api/confirm-item/{action}/{item_id}` and `/api/confirm-batch/{action}/{batch_id}` currently return a plain confirm modal (`fragments/confirm_action.html`). Extend them so that when `action == "cancel"`, they return the **form-bearing** variant that includes:

- A `<textarea name="reason">` with the default `"cancelled by operator"`.
- A `<input type="checkbox" name="to_draft">` (for item-cancel) or `name="reset_items"` (for batch-cancel) with a clear label.
- The `<form method="post" action="…">` posts to the corresponding cancel endpoint.

Approach:
- Add a new fragment file `dashboard/templates/fragments/confirm_action_form.html` that uses the (extended) `confirm_dialog` macro with a `form_html` parameter. **Frontend (S03) creates the new fragment file and extends the macro.** Your job in S01 is to render the right template name from the GET handler.
- Keep the existing `fragments/confirm_action.html` for non-cancel actions — do not break approve / pause / resume / restart.
- Branch in the handler:
  ```python
  template_name = (
      "fragments/confirm_action_form.html"
      if action == "cancel"
      else "fragments/confirm_action.html"
  )
  ```
- The template context for the cancel variant must include `default_reason="cancelled by operator"` and `reset_field_name` (`"to_draft"` for items, `"reset_items"` for batches) and `reset_field_label` (`"Also reset item to draft (re-runnable)"` / `"Also reset member items to draft (re-runnable)"`).

### 4. Update `_ACTION_LABELS` copy

Update the `"cancel"` entries in both `_ACTION_LABELS` dicts (item and batch sections) so the title/description reflect the destructive teardown. Suggested copy:

- Item cancel — title: `"Cancel Item?"`, description: `"Cancels this work item. Kills any running step process, marks pending steps as skipped, and tears down its worktree. Optionally resets to draft so it can be redesigned."`, confirm label: `"Cancel Item"`, danger: `True`.
- Batch cancel — title: `"Cancel Batch?"`, description: `"Cancels this batch and every non-terminal item in it. Kills running steps, tears down worktrees, and marks each work item as cancelled (or resets to draft if you tick the checkbox)."`, confirm label: `"Cancel Batch"`, danger: `True`.

### 5. Keep allowed-status sets in sync with the service layer

Do **not** re-implement status guards in the router — `orch.cancel.cancel_batch` / `cancel_work_item` already validate. The router's only responsibility is parsing the request and translating exceptions. This is Invariant 1 of the design doc.

### 6. Imports & types

- Import `orch.cancel.cancel_batch` and `orch.cancel.cancel_work_item` lazily inside the handler (consistent with the existing pattern of inline imports for cross-package calls), OR at module top — match whatever pattern is closest in `actions.py`.
- Add a `from fastapi import Form` import if not already present.
- Type-annotate return as `Response` (existing pattern).

### 7. Tests in this step

This is an `api-impl` step, NOT a tests-impl step. Write **only** enough TDD-RED tests in `tests/dashboard/` to anchor the new API contract (≤4 small TestClient tests). The dedicated test step S05 expands coverage to every AC/Boundary row. Suggested S01 anchors:

1. `test_cancel_item_calls_service_layer_with_form_params` — monkey-patch `orch.cancel.cancel_work_item`, POST with form data, assert call kwargs.
2. `test_cancel_batch_calls_service_layer_with_form_params` — same pattern.
3. `test_cancel_item_maps_lookup_error_to_404`.
4. `test_cancel_item_maps_active_batch_value_error_to_409`.

Capture the RED run line for each (`tdd_red_evidence` in the result contract).

## Project Conventions

Read `CLAUDE.md` (root, `dashboard/`, `orch/`). Hard rules that matter for this step:

- Routers are thin: validate, delegate to `orch/`, render fragment. No business logic in `actions.py`.
- `dependencies.get_db()` is the only DB injection point. Use it.
- No `navigator.clipboard` direct calls (not applicable here).
- No new Tailwind dynamic class construction.
- Tests follow the testcontainer pattern in `tests/dashboard/` — do not connect to live DB.

## TDD Requirement

RED → GREEN → REFACTOR. Confirm the RED failure is a real `AssertionError` (not an `ImportError` / fixture error). Capture the failing line as `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting complete:

1. `make format` — auto-fixes formatting. If it reformats, inspect and re-stage.
2. `make typecheck` — zero errors on files you touched.
3. `make lint` — zero new errors.

## Test Verification

Run **only** the new test file(s) you wrote in S01:

```bash
uv run pytest tests/dashboard/test_actions_cancel_batch.py tests/dashboard/test_actions_cancel_item.py -v
```

Do NOT run the full test suite — S07–S14 own the gates.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "API",
  "work_item": "F-00082",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/actions.py",
    "tests/dashboard/test_actions_cancel_batch.py",
    "tests/dashboard/test_actions_cancel_item.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_actions_cancel_batch.py::test_cancel_batch_calls_service_layer_with_form_params — AssertionError: …",
  "blockers": [],
  "notes": "Confirm-dialog fragment file (confirm_action_form.html) is referenced by name only in this step; S03 (Frontend) creates the file."
}
```
