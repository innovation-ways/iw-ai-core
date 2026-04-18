# CR-00010_S03_Frontend_prompt

**Work Item**: CR-00010 — Research items auto-complete without manual approval
**Step**: S03
**Agent**: frontend-impl

---

## Input Files

- `ai-dev/active/CR-00010/CR-00010_CR_Design.md` — design document (read first)
- `ai-dev/active/CR-00010/reports/CR-00010_S01_Backend_report.md` — S01 report (backend contract)
- `dashboard/routers/actions.py` — approve / unapprove route handlers
- `dashboard/routers/project_pages.py` — work-item detail + batch-queue views (and sibling routers if the queue lives elsewhere)
- `dashboard/templates/**` — grep for every template that renders an approve/unapprove form
- `orch/db/models.py` — `WorkItem`, `WorkItemType`, `WorkItemStatus` (for queries)
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00010/reports/CR-00010_S03_Frontend_report.md`

## Context

Dashboard changes — the backend now rejects approve/unapprove and batch-create for research items. The UI must reflect this:

1. Item-detail page hides the approve/unapprove buttons/forms when the item is a research item and replaces them with an inline notice.
2. The batch-queue list (approved work items eligible to enter a new batch) excludes research items from both the backend query and the rendered template.
3. The dashboard approve/unapprove action routes reject research items with an htmx-friendly error matching the existing invalid-transition pattern.

## Requirements

### 1. Audit templates — find every approve/unapprove render site

1. `grep -rn "approve\|unapprove" dashboard/templates/` — enumerate every template that renders an approve or unapprove button/form.
2. List them in your report under `audited_templates:` so reviewers can verify coverage.
3. For each one that renders on a work-item context (detail page, row action, etc.), add a Jinja guard:
   ```jinja
   {% if item.item_type.value != 'Research' %}
     {# existing approve/unapprove form #}
   {% else %}
     <p class="text-sm text-muted">
       Research items auto-complete when the research document is created.
     </p>
   {% endif %}
   ```
4. The guard predicate is `item.item_type.value != 'Research'`. Confirm the ORM enum serializes as the string `"Research"` in Jinja (`WorkItemType.Research.value == "Research"` per `orch/db/models.py:48-52`).
5. If multiple templates inherit from a shared partial that renders the action buttons, put the guard in the partial, not in every inheritor. Avoid duplication.

### 2. Batch-queue backend filter

1. Find the route handler that feeds the batch-queue view — likely in `dashboard/routers/project_pages.py` or a sibling (`batch_pages.py`, `project_dashboard.py`). It will contain a SELECT that filters by `WorkItem.status == WorkItemStatus.approved`.
2. Add `WorkItem.item_type != WorkItemType.Research` to the WHERE clause:
   ```python
   stmt = (
       select(WorkItem)
       .where(
           WorkItem.project_id == project_id,
           WorkItem.status == WorkItemStatus.approved,
           WorkItem.item_type != WorkItemType.Research,
       )
       # ... existing order_by / limit
   )
   ```
3. If the query is factored into a service helper (e.g., `dashboard/services/` or `orch/`), update it there and verify all call sites use the new contract.
4. Import `WorkItemType` in the router/service module if not already.

### 3. Batch-queue template filter (defense in depth)

1. In the template that renders the batch-queue list, wrap the row render in `{% if item.item_type.value != 'Research' %}` as a second line of defense. This also hides any research item that might have been included via a stale cache or manual DB edit.
2. If the template already iterates over a backend-filtered list (step §2), the `{% if %}` never triggers in practice — but it documents intent and guards against the filter being accidentally removed.

### 4. Approve / Unapprove route rejection

In `dashboard/routers/actions.py` (or wherever the POST handlers for approve/unapprove live):

1. After loading the work item and confirming ownership, add a research guard BEFORE the existing status-transition logic:
   ```python
   if work_item.item_type == WorkItemType.Research:
       # Match the existing invalid-transition HTTP contract — pick whichever
       # response shape the other error branches already use (HTMLResponse with
       # htmx hx-trigger, HTTPException, or a flash-message redirect).
       return _research_action_rejected_response(...)
   ```
2. The response body/content should read:
   - For approve: `"Research items cannot be approved — they auto-complete when the research document is created."`
   - For unapprove: `"Research items do not use the approval workflow."`
3. Match the response style of existing invalid-transition branches in the same file — if they return `HTTPException(400, ...)`, do that. If they return `HTMLResponse` with an `hx-trigger` header for htmx toast, do that instead. Consistency > novelty.
4. Import `WorkItemType` at the module top if not already.

### 5. Research-item detail page — inline notice

When rendering the work-item detail page for a research item, in place of the approve/unapprove section (now hidden per §1), render the inline notice:

```jinja
<section class="rounded border border-muted bg-muted/20 p-3 text-sm text-muted">
  Research items auto-complete when the research document is created via
  <code>iw doc-update</code>. They do not use the approval workflow.
</section>
```

Use the existing dashboard CSS utility classes. Do NOT add new CSS.

### 6. Keep scope narrow

- Do NOT touch `dashboard/static/` unless the Jinja changes require a tiny JS adjustment (unlikely — none expected).
- Do NOT redesign the item-detail page layout.
- Do NOT modify `orch/` — that's S01's scope.
- Do NOT add tests — that's S05's scope.

## Project Conventions

Read `dashboard/CLAUDE.md`:

- FastAPI + Jinja2 + htmx; no build step, no bundler.
- Autoescape is on by default — `{{ item.item_type.value }}` is safe in text context. Do NOT use `| safe`.
- Business logic stays in `orch/` — routers are thin glue, templates are presentation.
- No inline JS in templates unless absolutely necessary (none needed here).

Hard rules from `CLAUDE.md`:

- **NEVER** use `agent-browser` — use `playwright-cli` (irrelevant for this step; you are not browsing).
- **NEVER** hardcode ports — no change here.

## TDD Requirement

You MAY add template-rendering smoke tests if the existing test suite has patterns for them (check `tests/integration/` for dashboard tests). The full test coverage is owned by S05 — do NOT duplicate.

## Test Verification (NON-NEGOTIABLE)

1. `uv run ruff check dashboard/`
2. `uv run ruff format --check dashboard/`
3. `uv run mypy dashboard/`
4. `make test-unit` (ensure no regressions introduced by router changes)
5. Sanity check: open the project's code with a local dashboard running (if convenient; the browser verification is formally S14). If the dev env is not running locally, skip — S14 covers it.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "CR-00010",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/actions.py",
    "dashboard/routers/project_pages.py",
    "dashboard/templates/<exact paths discovered>"
  ],
  "audited_templates": [
    "<list every template grepped for approve/unapprove>"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Record the exact query helper modified for the batch-queue filter and the response shape used by the approve/unapprove rejection branches."
}
```
