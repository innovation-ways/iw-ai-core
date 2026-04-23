# F-00060_S05_API_prompt

**Work Item**: F-00060 — Hybrid Code Q&A retrieval
**Step**: S05 — Re-index endpoint
**Agent**: api-impl

---

## ⛔ Docker is off-limits

Same rules as S01.

---

## Input Files

- `ai-dev/active/F-00060/F-00060_Feature_Design.md` — see *API Changes*, *Boundary Behavior / Concurrent re-index request*
- `ai-dev/active/F-00060/reports/F-00060_S02_Backend_report.md` — `DocIndexJob` ORM shape
- `dashboard/routers/code_ui.py` — existing code-index-related endpoints to mirror (look for the POST that enqueues a `CodeIndexJob`)
- `dashboard/templates/fragments/code_job_status.html` — existing fragment to reuse

## Output Files

- `ai-dev/active/F-00060/reports/F-00060_S05_API_report.md` (new)
- `dashboard/routers/code_ui.py` (modified — new endpoint)

## Context

A one-line button in the Code view needs a server endpoint that enqueues a
`DocIndexJob`. The actual execution happens in S04's poller and S02's
runner.

## Requirements

### 1. `POST /project/{project_id}/api/code/reindex-docs`

Handler name: `reindex_docs` (or whatever matches local naming for the
code-reindex endpoint). Steps:

- Resolve the project from `project_id`; 404 if not found (match existing
  route handling).
- Check if a `doc_index_jobs` row for this project already has `status IN
  ('queued', 'running')` — if so, return 409 with an htmx fragment that
  says "A doc re-index is already running for this project" and includes a
  link to the Jobs view.
- Otherwise INSERT a new `doc_index_jobs` row with:
  - `id = str(uuid.uuid4())`
  - `project_id = project_id`
  - `status = 'queued'`
  - `provider`, `llm_model`, `embed_model`, `index_tier` sourced from the
    project's `CodeUnderstandingConfig` (same helper the code-reindex
    endpoint uses).
  - `triggered_at = now()` (DB default fires).
- Commit, then return 200 with an htmx fragment (rendered via Jinja2) that
  shows the new row using the existing `code_job_status.html` fragment —
  extended (or parameterised) to accept either job type. The frontend
  target is the existing Jobs drawer / inline status area.

### 2. No direct runner launch

Do NOT launch the runner from this endpoint. The daemon poller (S04)
dequeues and launches. Keep the request fast (<100 ms).

### 3. Authorization guard

Reuse whatever guard the existing code-reindex endpoint uses (project
access check, CSRF token if present). Match it exactly; no new auth model.

### 4. No new router file

Add the endpoint to the existing `code_ui.py` router; do not create a new
router module.

## Project Conventions

Read `dashboard/CLAUDE.md`. FastAPI + htmx + Jinja2. Fragments live under
`dashboard/templates/fragments/`. Session access via the router's existing
dependency injection. Return `HTMLResponse` for htmx fragments, not JSON.

## TDD Requirement

1. **RED**: `tests/integration/test_reindex_docs_endpoint.py`:
   - POST with no running job → 200, fragment contains `queued` state and
     the new job id.
   - POST when a job is `queued` for the same project → 409.
   - POST when a job is `running` for the same project → 409.
   - POST for an unknown project → 404.
   - POST writes exactly one row to `doc_index_jobs`; the row has correct
     `project_id`, `status='queued'`, and the expected config fields.
2. **GREEN**: implement.
3. **REFACTOR**: verify the existing code-reindex endpoint is untouched.

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — pass.
2. `make lint` + `make typecheck` — pass.

## Subagent Result Contract

Standard JSON with `step: "S05"`, `agent: "api-impl"`, `work_item: "F-00060"`.
