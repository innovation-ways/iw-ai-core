# F-00021_S01_Frontend_prompt

**Work Item**: F-00021 — Research Panel in AI Dashboard
**Step**: S01
**Agent**: Frontend
**Parallel With**: None — first step

---

## Input Files

- `ai-dev/active/F-00021/F-00021_Feature_Design.md` — Design document

## Output Files

- `ai-dev/active/F-00021/reports/F-00021_S01_Frontend_report.md`

## Context

You are adding a Research panel to the IW AI Core dashboard. This is a near-exact parallel
of the existing Docs panel. Read the existing docs implementation thoroughly and mirror it.

**IMPORTANT — Repository location**: All code changes go in:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

## Architecture References

Read these files completely before implementing:

- `dashboard/routers/docs.py` — Copy this pattern exactly for `research.py`
- `dashboard/templates/docs_library.html` — Copy this pattern for `research_library.html`
- `dashboard/templates/docs_detail.html` — Copy this pattern for `research_detail.html`
- `dashboard/templates/base.html` (lines 109–165) — Where to add the sidebar Research link
- `dashboard/app.py` (lines 90–105) — Where to register the new router
- `orch/doc_service.py` — `list_docs()`, `get_doc()`, `list_doc_versions()` methods
- `orch/db/models.py` — `DocType.research`, `DocStatus`, `EditorialCategory`

## Previous Steps

This is the first implementation step. Depends on F-00020 (DocType.research enum value must exist).

## Requirements

### 1. Create `dashboard/routers/research.py`

Mirror `docs.py` with these differences:
- Module docstring: "Research router — project-level research document library and detail pages."
- URL prefix: `prefix="/project/{project_id}"` (same as docs)
- **List route**: `GET /project/{project_id}/research`
  - Filter: `svc.list_docs(project_id, doc_type=DocType.research)` — research docs only
  - Template: `research_library.html`
  - Context variables: same as docs_library + `categories` (list of `EditorialCategory` values)
- **Detail route**: `GET /project/{project_id}/research/{doc_id}`
  - Guard: after fetching doc, verify `doc.doc_type == DocType.research` — if not, raise 404
  - Template: `research_detail.html`
  - Context variables: same as docs_detail

### 2. Create `dashboard/templates/research_library.html`

Mirror `docs_library.html` with these changes:
- Page title: "Research" (not "Documentation Library")
- Empty state message: "No research documents yet. Use `/iw-research` to create one."
- Add an "Editorial Category" filter dropdown (alongside the Status filter)
- Table columns: ID, Title, Category, Status, Created
- Each row links to `/project/{project_id}/research/{doc_id}`
- Apply client-side filter via existing htmx/Alpine.js patterns used in the docs template

### 3. Create `dashboard/templates/research_detail.html`

Mirror `docs_detail.html` with these changes:
- Page title: doc.title + " — Research"
- Breadcrumb: Research → {doc.title}
- Back link: `/project/{project_id}/research`
- Show `editorial_category` as "Mode" in the metadata sidebar
- Show rendered markdown content (use `content_html` — same as docs)
- Show version history list

### 4. Modify `dashboard/templates/base.html`

Add a "Research" link immediately after the "Docs" link in the sidebar (around line 140):

```html
<a href="/project/{{ current_project.id }}/research"
   class="flex items-center px-2 py-1.5 rounded text-sm transition-colors
          {% if request.url.path.startswith('/project') and '/research' in request.url.path %}
            bg-sidebar-accent text-sidebar-accent-foreground font-medium
          {% else %}
            text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground
          {% endif %}">
  <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/>
  </svg>
  <span>Research</span>
</a>
```

Only show the Research link when `current_project` is set (same guard as other project-scoped links).

### 5. Modify `dashboard/app.py`

Import and register the research router:
```python
from dashboard.routers import research  # add to imports
# ...
app.include_router(research.router)  # add after docs.router line
```

## Mandatory Patterns

- Follow the exact same code patterns as `docs.py` — no new patterns
- Jinja2 templates: use `{{ content_html | safe }}` for rendered markdown
- All routes return `HTMLResponse` and use `templates.TemplateResponse`
- Follow existing Tailwind CSS class patterns from docs templates
- No JavaScript — use htmx for any dynamic behavior (match existing docs pattern)

## TDD Requirement

Write integration tests before implementing to guide your work (see S03 for full test spec).
At this step, minimally run the existing test suite to ensure no regressions.

## Test Verification

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/python -m ruff check dashboard/
.venv/bin/python -m mypy dashboard/routers/research.py
.venv/bin/pytest tests/integration/test_dashboard_pages.py -x --timeout=120 -q
```

Existing dashboard page tests must continue to pass.

## Constraints

- Do NOT modify `docs.py`, `docs_library.html`, or `docs_detail.html` — only create new files
- Do NOT add new dependencies
- Only modify `base.html` and `app.py` from existing files

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Frontend",
  "work_item": "F-00021",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/research.py",
    "dashboard/templates/research_library.html",
    "dashboard/templates/research_detail.html",
    "dashboard/templates/base.html",
    "dashboard/app.py"
  ],
  "tests_passed": true,
  "test_summary": "Existing dashboard tests: N passed",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
