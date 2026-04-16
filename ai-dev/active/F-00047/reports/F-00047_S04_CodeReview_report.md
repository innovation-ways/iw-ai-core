# F-00047 S04 — Code Review: Frontend Templates + JS

## Review Result: PASS

## Files Reviewed

| File | Verdict |
|------|---------|
| `dashboard/templates/base.html` | PASS |
| `dashboard/templates/project_code.html` | PASS |
| `dashboard/templates/fragments/nav_projects.html` | PASS |
| `dashboard/templates/fragments/code_job_status.html` | PASS |
| `dashboard/templates/fragments/code_empty_state.html` | PASS |
| `dashboard/templates/fragments/code_architecture_view.html` | PASS |
| `dashboard/templates/fragments/code_job_report.html` | PASS |
| `dashboard/routers/code_ui.py` (context variables) | PASS |

## Critical Issues
None.

## Minor Issues
None.

## Suggestions (optional)
1. **Dropdown menu `aria-label`** — `div#code-dropdown-menu` has `role="menu"` but could benefit from `aria-label="Code actions menu"` for screen reader clarity. Not required by the checklist but good accessibility practice.
2. **Unused `arch_doc` context** — `code_architecture_view.html` receives `arch_doc` in its context but never references it in the template body (only `content_html` is used). Dead context, not a runtime error.

## Detailed Checklist

### Template Structure
- [x] `project_code.html` extends `base.html` (line 1)
- [x] All `fragments/code_*.html` do NOT extend `base.html`
- [x] `{% block title %}` set as `Code — {{ current_project.display_name }}` (line 3)
- [x] `current_project` passed to template and used for sidebar highlight
- [x] All Jinja2 template variables from route context are used correctly
- [x] `| safe` filter applied to `content_html` in `code_architecture_view.html` (line 28)

### Nav Link
- [x] "Code" link added to `nav_projects.html` after "Research" (line 22)
- [x] Link href is `/project/{{ project.id }}/code` — matches existing link format
- [x] Active state highlighting works via existing path-prefix logic

### Mermaid Integration
- [x] `mermaid.min.js` CDN script added to `base.html` after `marked.min.js` (line 80)
- [x] `mermaid.initialize({ startOnLoad: true, theme: 'default' })` called (lines 82-86)
- [x] `htmx:afterSwap` listener re-initializes `.mermaid:not([data-processed])` nodes (lines 277-284)
- [x] `[data-processed]` guard prevents re-rendering of already-processed diagrams
- [x] Route handler pre-processes fenced mermaid blocks via `_preprocess_mermaid()` (code_ui.py:59-61)

### SSE Client (code_job_status.html)
- [x] Uses vanilla JS `EventSource` — NOT `hx-ext="sse"`
- [x] `es.close()` called on `done` event (line 74) and on `onerror` (line 84)
- [x] DOM elements updated by ID via `getElementById` — no jQuery/framework
- [x] Progress bar width set via `element.style.width = pct + '%'` (line 63)
- [x] Elapsed timer uses `setInterval` and is cleared when EventSource closes (lines 87-95)
- [x] After `done` event: `htmx.ajax()` refreshes both `#code-status-panel` and `#code-architecture-panel` (lines 75-78)
- [x] `JSON.parse` wrapped in try/catch (lines 69-80)

### Dropdown Button
- [x] Uses pure CSS/JS — no third-party components
- [x] `toggleCodeDropdown()` function defined and called by button's `onclick` (lines 92-99)
- [x] Outside-click listener closes the dropdown (lines 100-106)
- [x] All three POST buttons present: full index, incremental, regen-map
- [x] Correct `hx-post` URLs: `/api/code/index`, `/api/code/reindex`, `/api/code/regen-map`
- [x] `hx-target="#code-status-panel"` and `hx-swap="innerHTML"` on all three
- [x] Loading state: `htmx:beforeRequest` disables buttons (lines 109-115), `htmx:afterRequest` re-enables (lines 117-125)

### Styling and Accessibility
- [x] No dynamic class string construction
- [x] Dark mode variants present (`dark:bg-*`, `dark:text-*`, `dark:border-*`)
- [x] Color tokens used: `bg-card`, `border-border`, `text-foreground`, `text-muted-foreground`, `bg-primary`, `text-primary-foreground`
- [x] Progress bar: `role="progressbar"`, `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`
- [x] Spinner: `aria-label="Loading"` and `role="status"`
- [x] Dropdown button: `aria-expanded="false"` (dynamically updated by JS)
- [x] Dropdown menu: `role="menu"`

### Empty State
- [x] Shows when `index_status` is None or `content_html` is falsy
- [x] "Generate Code Map" button present with correct `hx-post`
- [x] Provider/model info shown via `index_status.llm_model`

### Architecture View
- [x] `.prose-doc` CSS styles defined inline in `<style>` block (lines 7-27)
- [x] `.mermaid` CSS: `text-align: center`, `max-width: 100%` (lines 25-26)
- [x] Content scrollable with `overflow-y-auto` and `max-height: calc(100vh - 280px)`

### Job Report
- [x] Green color scheme: `bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800`
- [x] Duration from `last_completed_duration` context variable (lines 9-11)
- [x] Field names: `files_indexed`, `chunks_created`, `languages_detected`, `llm_model`, `embed_model`
- [x] No references to `chat_model`, `languages_json`, `duration_formatted`, or `completed_recently`
- [x] "Recent" check uses `last_completed_recent` context variable

### Context Variable Names (verified against code_ui.py)
- [x] `index_status.llm_model` — route passes `llm_model` (code_ui.py:105)
- [x] `index_status.level1_doc_markdown` — route passes `level1_doc_markdown` (code_ui.py:111)
- [x] `index_status.languages_detected` — route passes `languages_detected` (code_ui.py:110)
- [x] `intcomma` filter — confirmed registered in `app.py:113`
- [x] `timeago` filter — confirmed registered in `app.py:88,114`

## Quality Gates

`uv run ruff check dashboard/routers/code_ui.py`: **All checks passed**

## Notes

The previous S04 review incorrectly flagged `intcomma` and `timeago` as missing Jinja filters. Both are confirmed registered in `dashboard/app.py` (lines 88, 113-114).
