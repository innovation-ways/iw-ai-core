# F-00081_S04_API_prompt

**Work Item**: F-00081 -- Per-Item / Per-Step Agent + Model Override
**Step**: S04
**Agent**: api-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers in pytest are exempt.

## ⛔ Migrations: agents generate, daemon applies

S01 owns the migration. Do NOT touch alembic.

## Input Files

- `uv run iw item-status F-00081 --json` for runtime step state.
- `ai-dev/active/F-00081/F-00081_Feature_Design.md` (especially the API Changes section and AC1, AC4, AC6, AC7).
- `ai-dev/active/F-00081/reports/F-00081_S01_Database_report.md` and `F-00081_S02_Backend_report.md` — the schema and helpers you depend on.
- Existing files (read for patterns, edit minimally):
  - `dashboard/routers/actions.py` — htmx PATCH/POST patterns. Note `router = APIRouter(prefix="/project/{project_id}/api")` and helper `_emit` at line ~178.
  - `dashboard/dependencies.py` — `get_db()` dependency.
  - `dashboard/app.py` — router registration.
  - `dashboard/templates/components/confirm_dialog.html` — htmx fragment shape, if you choose to surface a confirm.

## Output Files

- `ai-dev/active/F-00081/reports/F-00081_S04_API_report.md`.
- New file: `dashboard/routers/runtime_overrides.py` (kept separate from `actions.py` to avoid bloating that module).
- Edits: `dashboard/app.py` to register the new router.

## Context

You are implementing the HTTP layer for the override controls. The frontend (S05) will call your endpoints via htmx. Read the design doc carefully — endpoints, validation rules, AC4 lock semantics, AC6 single-event audit, AC7 catalogue integrity.

## Requirements

### 1. Endpoint: GET `/project/{project_id}/api/runtime-options`

Returns enabled rows from `agent_runtime_options` ordered by `sort_order, id`. Response: JSON list of `{id, cli_tool, model, cli_label, model_label, display_name, is_default}`. Used by the frontend to populate the dropdowns. Cache header is fine (`Cache-Control: max-age=60`) — the catalogue is essentially static within a session.

### 2. Endpoint: PATCH `/project/{project_id}/api/item/{item_id}/runtime-override`

Form fields (htmx submits `application/x-www-form-urlencoded`):
- `option_id`: integer → set `work_items.agent_runtime_option_id`. Empty/absent → clear (set to NULL).

Validation:
- Item must exist and belong to `project_id` (404 otherwise).
- Item must have at least one editable step (status ∈ `{pending, failed, paused}`); otherwise return 400 with body `Item has no editable steps; cannot apply override.` (Boundary case: "User sets item-level override after the item is `done`".)
- `option_id`, if present, must reference an enabled row (404 otherwise).

On success: emit `runtime_override_changed` DaemonEvent (scope='item') via the helper from S02, return the htmx fragment that re-renders the row's CLI/Model badges (or 204 + `HX-Trigger` to re-fetch).

### 3. Endpoint: PATCH `/project/{project_id}/api/item/{item_id}/step/{step_id}/runtime-override`

Form fields: `option_id` (integer or empty).

Validation:
- Item + step exist (`(project_id, item_id, step_id)` triple).
- Step status ∈ `{pending, failed, paused}`. Otherwise return **409 Conflict** with body `Step is not editable (status=<status>).` (Boundary case: race transition mid-PATCH.)
- `option_id`, if present, references an enabled row.

On success: emit DaemonEvent (scope='step', step_ids=[step_id]) and return htmx fragment.

### 4. Endpoint: PATCH `/project/{project_id}/api/item/{item_id}/runtime-override/bulk`

Form fields: `option_id` (integer or empty).

Behaviour: in one transaction, update every step under the item whose status is in `{pending, failed, paused}`.

- If `option_id` is given, set `workflow_steps.agent_runtime_option_id = option_id` for those steps.
- If empty, clear the override.
- Steps with non-editable status are silently skipped (no error).
- Emit ONE DaemonEvent (scope='bulk', step_ids=[…all updated step_ids…]). When zero steps were updated, emit no event (boundary case).
- Return htmx fragment refreshing the steps table.

### 5. Catalogue integrity (AC7)

There is no API endpoint that mutates the catalogue in this feature (admin page is out of scope). The DB CHECK constraint from S01 is the enforcement; tests in S06 cover that. If you add a future write endpoint, validate that disabling/deleting `is_default=true` returns 400 — but do not add such an endpoint here.

### 6. Authorisation / actor capture

Use whatever auth context the existing `actions.py` endpoints rely on (likely the request session — read `dashboard/routers/actions.py` for the pattern). Pass an `actor` string to the audit helper. If the project has no real auth model (it does not appear to), use the request's `User-Agent` or a stable `"dashboard"` placeholder — match what other endpoints do.

### 7. Tests

Write dashboard TestClient tests at `tests/dashboard/test_runtime_overrides_api.py`:

- GET endpoint returns enabled rows in sort order.
- PATCH item endpoint sets, clears, and rejects invalid option ids; rejects non-editable items.
- PATCH step endpoint returns 409 on non-editable status.
- Bulk endpoint updates only editable steps and emits exactly one DaemonEvent (count via SELECT COUNT(*) on `daemon_events` before/after).
- Bulk endpoint with zero affected steps emits zero events.

## Project Conventions

Read `dashboard/CLAUDE.md`:

- Routers are thin — delegate to `orch/agent_runtime/audit.py` and to small helpers; do not embed business logic.
- htmx PATCHes return **HTML fragments** that replace `hx-target`, not JSON. The GET catalogue endpoint is the one JSON exception (it powers `<select>` population from JS or via Jinja partial — confirm with S05's choice; if S05 uses Jinja-rendered options, this endpoint may instead return an HTML `<option>` fragment).
- Use `Form(...)` for form fields, not Pydantic body models.
- Use the project's `_emit` / `_action_response` helpers in `actions.py` if appropriate (read them first).

## TDD Requirement

Tests first. Each endpoint has a happy-path test and at least one rejection test before implementation.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format` → `make typecheck` → `make lint`.

## Test Verification (NON-NEGOTIABLE)

`make test-frontend` (= `make test-dashboard`) and `make test-integration` must pass.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "api-impl",
  "work_item": "F-00081",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/runtime_overrides.py",
    "dashboard/app.py",
    "tests/dashboard/test_runtime_overrides_api.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
