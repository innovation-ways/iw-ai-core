# F-00090_S03_Frontend_prompt

**Work Item**: F-00090 -- Regression-rate tracking
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy applies. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

This step leaves migrations unchanged. Do NOT run `alembic upgrade head` against the live DB.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00090 --json`.
- `ai-dev/active/F-00090/F-00090_Feature_Design.md` — AC5 is your primary target.
- `ai-dev/active/F-00090/reports/F-00090_S01_Database_report.md` and `F-00090_S02_Backend_report.md`.
- `dashboard/routers/items.py` — existing Incident detail page; you will extend it.
- `dashboard/templates/fragments/` — directory for new htmx fragments. Read a few existing ones (e.g. `archive_batch_dialog.html`, `batch_items_rows.html`) for style.
- `orch/regression_link_service.py` (from S02) — the write path you call from the htmx endpoint.

## Output Files

- `ai-dev/active/F-00090/reports/F-00090_S03_Frontend_report.md` — step report.
- New: `dashboard/templates/fragments/regression_classification_form.html`
- New: `dashboard/templates/fragments/regression_suggestion_list.html`
- Modified: `dashboard/routers/items.py` (mount + endpoints)
- Modified: the Incident detail page template (insert form mount-point)
- New: `tests/dashboard/test_regression_classification_form.py`

## Context

You are implementing the **Incident classification form** on the Incident detail page. The form is htmx-driven and posts to a new endpoint that calls `orch/regression_link_service.classify()` (from S02). Acceptance criterion is AC5; relevant Boundary rows: unknown FK (validation error), no suggestion available (button hidden), re-classification (form re-renders with updated state).

Read the design first. Read `CLAUDE.md` and `dashboard/CLAUDE.md` for project conventions.

## Requirements

### 1. htmx form fragment

Create `dashboard/templates/fragments/regression_classification_form.html`. The form must contain:

- A searchable dropdown of prior **merged** work items in the same project (status == 'done'), with text and value showing `ID — title`. Implement search via an `hx-get` against a new `/project/{pid}/work-items/search` (or extend an existing search route — check `dashboard/routers/search.py`) returning a `<datalist>` or a filtered `<ul>` for `hx-target`. **Do not** load every work item into the DOM upfront for projects with many items.
- A free-text input for an optional commit SHA. Validate client-side that it matches `^[0-9a-f]{7,40}$` (use the `pattern` HTML attribute); the server re-validates.
- A radio group with three values: `regression`, `pre_existing`, `unknown`. No default — the operator must pick.
- When the backend has at least one heuristic suggestion (passed in by the route as `top_suggestion`), render an "Accept suggestion" button labelled with the suggestion's `work_item_id` (or SHA short-prefix). The button posts `accept_top=1` so the server uses `classified_by='heuristic:auto'`. When no suggestion exists, omit the button entirely.
- The form's `hx-post` targets `/project/{project_id}/item/{item_id}/regression-classify` and `hx-target` swaps the row fragment in place.

Create `dashboard/templates/fragments/regression_suggestion_list.html` for the suggestion preview list rendered above the form (links the heuristic candidates in rank order).

### 2. Routes in `dashboard/routers/items.py`

Add:

- `GET /project/{project_id}/item/{item_id}/regression-suggestions` → returns `regression_suggestion_list.html` rendered from `regression_link_service.suggest_introducer(...)`. Used by the form to lazy-load suggestions when the operator clicks "Refresh suggestions".
- `POST /project/{project_id}/item/{item_id}/regression-classify` → reads form fields, calls `regression_link_service.classify(...)`. On `ValueError`, returns the form re-rendered with an inline error message and HTTP 422. On success, returns the updated Incident detail row fragment.
- Insert a `{% include "fragments/regression_classification_form.html" %}` (or equivalent mount-point) in the Incident detail page template so the form appears on `/project/{pid}/item/I-NNNNN`.

The `classified_by` value is `f"operator:{current_user}"` for normal submits and `"heuristic:auto"` when `accept_top` is set. Look at existing routes in `dashboard/routers/items.py` to see how the current user identity is sourced — match that pattern.

### 3. Dashboard tests — `tests/dashboard/test_regression_classification_form.py`

Cover AC5 and the Boundary rows that flow through the UI:

- `test_form_renders_on_incident_detail_page` — GET the page, assert the form, the three radios, and the searchable input are present.
- `test_form_submit_persists_and_returns_row_fragment` — POST happy path; assert the response contains the updated row and the DB row was updated.
- `test_form_validation_error_on_unknown_fk` — POST with bogus `introduced_by`, assert 422 + inline error.
- `test_accept_suggestion_uses_heuristic_auto` — POST with `accept_top=1`, assert `classified_by == 'heuristic:auto'`.
- `test_suggestion_button_hidden_when_no_candidates` — render with `top_suggestion=None`, assert button absent.

Use the existing dashboard test fixtures (TestClient + testcontainer). Match the style of existing tests in `tests/dashboard/`.

### 4. RED-first discipline (NON-NEGOTIABLE)

Write the failing tests first. Capture an `AssertionError` from one test in `tdd_red_evidence`.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Key constraints:

- **MUST** keep Jinja2 `format`-filter calls `%`-style: `"%dm%02ds"|format(m, s)` — never `str.format`-style. See I-00075.
- Use htmx idioms — `hx-post`, `hx-target`, `hx-swap`. No new JS libraries.
- Plain CSS rules go in `dashboard/static/styles.css`; new Tailwind utilities only if the toolchain is healthy (otherwise plain CSS — see I-00067).
- All page routes are namespaced by `project_id` — never assume a single project.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Run only the new test file:

```bash
uv run pytest tests/dashboard/test_regression_classification_form.py -v
```

Do NOT run the full dashboard test suite — that is the `frontend-tests` QV gate.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "F-00090",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/items.py",
    "dashboard/templates/fragments/regression_classification_form.html",
    "dashboard/templates/fragments/regression_suggestion_list.html",
    "dashboard/templates/pages/<incident-detail-page>.html",
    "tests/dashboard/test_regression_classification_form.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "tests/dashboard/test_regression_classification_form.py: N passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_regression_classification_form.py::test_form_renders_on_incident_detail_page — AssertionError: 'regression-classification-form' not in response.text (RED before fragment added)",
  "blockers": [],
  "notes": ""
}
```
