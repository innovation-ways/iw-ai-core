# F-00041_S01_Frontend_prompt

**Work Item**: F-00041 — Interactive Document IDE — Guide Editor & Diff Viewer UI
**Step**: S01
**Agent**: Frontend
**Parallel With**: None — first step

---

## Input Files

- `ai-dev/active/F-00041/F-00041_Feature_Design.md` — Design document
- `dashboard/templates/docs_detail.html` — Page to extend with IDE tab
- `dashboard/templates/fragments/docs_diff.html` — Existing diff fragment (reference)
- `dashboard/routers/docs.py` — Router to extend with new htmx endpoints
- `dashboard/CLAUDE.md` — Dashboard conventions
- `orch/doc_service.py` — Service methods for guide CRUD

## Output Files

- `ai-dev/active/F-00041/reports/F-00041_S01_Frontend_report.md`

## Context

You are implementing the IDE tab UI for the document detail page in **iw-ai-core**.

**Repository location**:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

Read `dashboard/CLAUDE.md` for the htmx + Jinja2 + Tailwind stack conventions.

**Stack**: FastAPI + Jinja2 templates + htmx + Tailwind CDN. No build step.
**Pattern**: POST endpoints return HTML fragments (not redirects, not JSON). Fragments swap in-place.

## Requirements

### 1. Add IDE tab to `dashboard/templates/docs_detail.html`

Find the existing tab navigation (look for the version/history/diff tabs or similar tab bar).
Add an "IDE" tab that lazy-loads its content:

```html
<!-- IDE tab nav item -->
<button id="ide-tab-btn"
        hx-get="/project/{{ current_project.id }}/api/docs/{{ doc.doc_id }}/ide"
        hx-target="#ide-panel"
        hx-swap="innerHTML"
        hx-trigger="click once"
        class="tab-button ...">
  IDE
</button>
```

Add the target div below the tab content area:
```html
<div id="ide-panel" class="mt-4"></div>
```

### 2. Add 9 htmx endpoints to `dashboard/routers/docs.py`

Add these endpoints after the existing guide/diff endpoints. Follow the exact thin-router pattern
(validate inputs, call DocService methods, return template fragments). All routes are under the
existing `router = APIRouter(prefix="/project/{project_id}")`.

Endpoint list (copy from design doc §Scope):
- `GET /api/docs/{doc_id}/ide` → `fragments/docs_ide_tab.html`
- `GET /api/docs/{doc_id}/guide/type` → `fragments/docs_guide_type_editor.html`
- `POST /api/docs/{doc_id}/guide/type` → save via `DocService.save_type_guide`; return `fragments/docs_guide_type_editor.html` with saved content
- `GET /api/docs/{doc_id}/guide/instance` → `fragments/docs_guide_instance_editor.html`
- `POST /api/docs/{doc_id}/guide/instance` → save via `DocService.save_instance_guide`; return updated fragment
- `DELETE /api/docs/{doc_id}/guide/instance` → `DocService.delete_instance_guide`; return `fragments/docs_guide_instance_editor.html` (showing "inheriting" state)
- `GET /api/docs/{doc_id}/guide/sections` → `fragments/docs_guide_sections_panel.html` (list all sections from doc content via `extract_sections`)
- `POST /api/docs/{doc_id}/guide/sections/{section_name}` → `DocService.save_section_guide`; return updated section row
- `DELETE /api/docs/{doc_id}/guide/sections/{section_name}` → `DocService.delete_section_guide`; return 204 or cleared section row

For POST endpoints, read the guide_md from form body: `guide_md: str = Form(...)`.

### 3. Create `dashboard/templates/fragments/docs_ide_tab.html`

Two-column layout:
- Left panel (60%): Guide Editor (type guide, instance guide, section guides)
- Right panel (40%): Section Diff Viewer

Left panel loads via htmx: `hx-get="/api/docs/{doc_id}/guide/type"` etc. on mount (use `hx-trigger="load"` on inner divs).
Right panel shows version selector and diff; loads diff sections panel inline.

### 4. Create `dashboard/templates/fragments/docs_guide_type_editor.html`

```html
<div class="p-4 border rounded-lg bg-card">
  <h3 class="font-semibold text-sm mb-2">Type Guide
    <span class="text-xs text-muted-foreground ml-1">({{ doc_type }} default)</span>
  </h3>
  <form hx-post="/project/{{ project_id }}/api/docs/{{ doc_id }}/guide/type"
        hx-target="this" hx-swap="outerHTML">
    <textarea name="guide_md" rows="12"
              class="w-full font-mono text-xs border rounded p-2 bg-background resize-y"
              placeholder="No type guide configured — leave empty to inherit default.">{{ guide_md or '' }}</textarea>
    <button type="submit"
            class="mt-2 px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded hover:bg-primary/90">
      Save Type Guide
    </button>
  </form>
</div>
```

### 5. Create `dashboard/templates/fragments/docs_guide_instance_editor.html`

Similar to type editor, but with a "Delete Override" button that sends `hx-delete`.
Show a muted message "Inheriting from type guide" when `instance_guide` is None.

### 6. Create `dashboard/templates/fragments/docs_guide_sections_panel.html`

For each section in `sections` (from `extract_sections(doc.content)`):
- Show section name as header
- Textarea with the current `section_guide` (empty if not set)
- Save button (POST to `/guide/sections/{section_name}`)

If `sections == ["Document"]`, show a note: "No H2 headings — editing 'Document' guide"

### 7. Create `dashboard/templates/fragments/docs_section_diff_panel.html`

Version selector (two number inputs for v1 and v2) with a "Compare" button that:
- Loads from `/api/docs/{doc_id}/diff/sections?v1=N&v2=N` (JSON)
- Renders a list of sections with status badges (Added, Removed, Changed, Unchanged)
- Each "Changed" section is expandable to show the unified diff

## Project Conventions

- Tailwind classes only — no custom CSS
- `hx-swap="outerHTML"` on forms so the form re-renders with saved state
- Use existing `fragments/toast_message.html` for success/error feedback
- Templates in `fragments/` must NOT extend `base.html`

## Test Verification

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/python -m ruff check dashboard/ tests/
.venv/bin/python -m mypy dashboard/routers/docs.py
```

Manually verify the IDE tab loads at: http://localhost:9900/project/iw-ai-core/docs/<any_doc_id>

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Frontend",
  "work_item": "F-00041",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/docs_detail.html",
    "dashboard/routers/docs.py",
    "dashboard/templates/fragments/docs_ide_tab.html",
    "dashboard/templates/fragments/docs_guide_type_editor.html",
    "dashboard/templates/fragments/docs_guide_instance_editor.html",
    "dashboard/templates/fragments/docs_guide_sections_panel.html",
    "dashboard/templates/fragments/docs_section_diff_panel.html"
  ],
  "tests_passed": true,
  "test_summary": "N/A — lint and typecheck only at this step",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
