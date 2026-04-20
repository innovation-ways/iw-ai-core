# F-00056_S05_API_prompt

**Work Item**: F-00056 -- Work Item Execution Report — Retry Pattern & Pain-Point Visibility
**Step**: S05
**Agent**: api-impl

---

## Input Files

- `ai-dev/active/F-00056/F-00056_Feature_Design.md` -- Design document (read API Changes, AC2, AC8, AC10, Boundary Behavior rows on dashboard routes, Invariant 6, Invariant 7)
- `ai-dev/active/F-00056/reports/F-00056_S04_CodeReview_report.md` -- S04 verdict
- `orch/daemon/execution_report.py` -- `assemble_execution_report` (from S03) — call this from the route handler
- `dashboard/routers/items.py:823-1024` -- existing item-detail tab routes (reference pattern)
- `dashboard/routers/items.py` (same file) existing `item_tab_fix_cycles()` (line ~1002) and `item_tab_reports()` (line ~880) -- the pattern to mirror
- `dashboard/templates/pages/project/item_detail.html` -- tab bar (read-only in this step; modified in S07)
- `dashboard/CLAUDE.md` -- dashboard conventions

## Output Files

- `ai-dev/active/F-00056/reports/F-00056_S05_API_report.md` -- Step report

## Context

You are adding two routes to `dashboard/routers/items.py` that serve the execution report. Both call `assemble_execution_report(session, project_id, work_item_id)` from `orch/daemon/execution_report.py` (S03) and render the Jinja2 template. Templates are owned by S07; this step assumes the templates exist at the paths specified and does not block on them — the test in S09 will verify end-to-end rendering.

## Requirements

### 1. Add the tab fragment route

In `dashboard/routers/items.py`, mirroring `item_tab_fix_cycles()` or `item_tab_reports()`:

```python
@router.get("/project/{project_id}/item/{work_item_id}/tab/execution-report")
def item_tab_execution_report(
    project_id: str,
    work_item_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse: ...
```

Behavior:

- Query `WorkItem` by `(project_id, work_item_id)`; if not found, return HTTP 404 with the existing error template/response pattern used by sibling routes.
- Call `assemble_execution_report(session, project_id, work_item_id)`.
- Render `dashboard/templates/fragments/item_execution_report.html` with the `ExecutionReportData` as template context plus anything the existing fragments pass (Request, etc.).
- Return the rendered HTML as `HTMLResponse` (this is an htmx fragment — no `base.html` wrapping). Match exactly the return signature used by the other `item_tab_*` functions.

### 2. Add the standalone page route

```python
@router.get("/project/{project_id}/item/{work_item_id}/execution-report")
def item_execution_report_page(
    project_id: str,
    work_item_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse: ...
```

Behavior:

- Same 404 handling.
- Same `assemble_execution_report` call.
- Render `dashboard/templates/pages/project/item_execution_report.html` (wraps the fragment in `base.html`).
- Return `HTMLResponse`.

### 3. No changes to existing routes or templates

Both of the new routes are strictly additive. Do NOT modify `item_tab_reports`, `item_tab_fix_cycles`, `item_tab_logs`, or any other existing function. Do NOT modify `item_detail.html` (that's S07).

### 4. Session and error handling

- Use the project's existing session dependency pattern from sibling routes (`Depends(get_session)` or whatever pattern they use — match, don't invent).
- Wrap DB calls in try/except only if sibling routes do; match the existing error-handling style.
- Do not swallow unexpected exceptions — let FastAPI surface 500s for genuine errors.

### 5. Route registration

If `dashboard/routers/items.py` uses an `APIRouter` instance that's already included in the FastAPI app, your new routes are registered automatically. Verify by starting the dashboard locally (`make dashboard-start`) and curling the route for a known item — or rely on the integration test in S09. Do not add any new router inclusion code to `dashboard/app.py` unless sibling routes required explicit registration.

### 6. No SSE, no htmx fragments beyond the tab

Both routes return simple server-rendered HTML. No SSE, no htmx swap beyond what the tab-bar's existing `hx-get` pattern already provides. Do not introduce new JS.

## Project Conventions

Read `dashboard/CLAUDE.md` for:

- FastAPI routing conventions (path params, dependencies, response classes)
- Jinja2 template lookup paths (`templates/fragments/` vs `templates/pages/`)
- Session injection pattern
- 404 and error templates

## TDD Requirement

Follow TDD:

1. **RED**: Write a failing route test in `tests/integration/test_execution_report_dashboard_route.py` (the file lives in S09's scope, but a minimal placeholder here is fine). Assert HTTP 200 for a seeded item and HTTP 404 for an unknown item, both for the tab and standalone routes.
2. **GREEN**: Implement the routes.
3. **REFACTOR**: Keep the two handlers DRY where sensible, but do not over-abstract.

S09 will expand integration coverage.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration`
3. `uv run ruff check dashboard/`
4. `uv run mypy dashboard/`

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "api-impl",
  "work_item": "F-00056",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/items.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
