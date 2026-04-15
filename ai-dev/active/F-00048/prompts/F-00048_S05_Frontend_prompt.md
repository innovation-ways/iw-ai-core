# F-00048_S05_Frontend_prompt

**Work Item**: F-00048 -- Code Understanding: Module + Symbol Views
**Step**: S05
**Agent**: frontend-impl

---

## Input Files

- `ai-dev/active/F-00048/F-00048_Feature_Design.md` -- Design document
- `ai-dev/work/F-00048/reports/F-00048_S03_API_report.md` -- API endpoints implemented in S03
- `dashboard/templates/base.html` -- Layout skeleton
- `dashboard/templates/fragments/` -- Existing fragment templates for pattern reference (includes `code_architecture_view.html` from F-00047 — the file you will be modifying)
- `dashboard/templates/project_code.html` -- F-00047's Code tab page (do NOT modify)

## Output Files

- `dashboard/templates/fragments/code_module_cards.html` -- Module cards grid fragment (**create**)
- `dashboard/templates/fragments/code_module_detail.html` -- Level 2 module detail fragment (**create**)
- `dashboard/templates/fragments/code_symbol_panel.html` -- Level 3 inline symbol panel fragment (**create**)
- `dashboard/templates/fragments/code_module_spinner.html` -- Loading spinner fragment (**create**)
- `dashboard/templates/fragments/code_architecture_view.html` -- **modify** F-00047's architecture fragment to add `#code-components-section`, `#code-detail-panel`, and the loading spinner container below the Mermaid diagram. Do NOT modify `project_code.html` directly.
- `ai-dev/work/F-00048/reports/F-00048_S05_Frontend_report.md` -- Step report

## Context

You are implementing the frontend for **F-00048: Code Understanding: Module + Symbol Views**.

The API endpoints from S03 are already implemented. Your job is to build the htmx-driven UI components that call those endpoints and render the three navigation levels: module cards (Level 1 view), module detail (Level 2 view), and inline symbol explanation (Level 3 view).

Read the design document, `CLAUDE.md`, and `dashboard/CLAUDE.md` before writing any templates. Study the existing fragment templates to understand the project's htmx patterns, Tailwind class usage, and Jinja2 conventions.

**Critical dashboard rules**:
- Fragments in `templates/fragments/` must NOT extend `base.html`
- Tailwind loaded from CDN — no build step, no purge; avoid dynamic class construction (e.g., no `"text-" + color`)
- htmx pattern: actions trigger `hx-get`/`hx-post` endpoints that return HTML fragments replacing `hx-target` elements
- No JavaScript frameworks — htmx + minimal vanilla JS only

## Requirements

### 1. templates/fragments/code_module_cards.html

This fragment is loaded via htmx after the Level 1 architecture doc renders. It shows the list of modules as clickable cards.

The template receives a context variable `modules` (list of dicts: `name`, `path`, `description`, `slug`) and `project_id`.

```html
<!-- Renders a grid of module cards below the Mermaid diagram -->
<!-- Called via hx-get="/api/projects/{project_id}/code/modules" -->
<!-- hx-target="#code-components-section" -->
<div id="code-components-section">
  {% if modules %}
    <h3 class="...">Components</h3>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {% for module in modules %}
        <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
          <div class="font-mono text-sm text-gray-500">{{ module.path }}</div>
          <div class="font-semibold mt-1">{{ module.name }}</div>
          <div class="text-sm text-gray-600 mt-1 line-clamp-2">{{ module.description }}</div>
          <button
            class="mt-3 text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
            hx-get="/api/projects/{{ project_id }}/code/modules/{{ module.slug }}"
            hx-target="#code-detail-panel"
            hx-swap="innerHTML"
            hx-indicator="#code-loading-spinner"
          >
            View details →
          </button>
        </div>
      {% endfor %}
    </div>
  {% else %}
    <p class="text-sm text-gray-500 italic">No components found in architecture doc.</p>
  {% endif %}
</div>
```

Adapt the exact Tailwind classes to match the project's existing style. Study existing card components in the codebase.

### 2. templates/fragments/code_module_spinner.html

A simple loading indicator shown while Level 2 content is being generated.

```html
<!-- Shown via hx-indicator while Level 2 is loading -->
<div id="code-loading-spinner" class="htmx-indicator flex items-center gap-2 py-4">
  <svg class="animate-spin h-5 w-5 text-blue-500" ...></svg>
  <span class="text-sm text-gray-600">Generating module analysis...</span>
</div>
```

Use the htmx indicator pattern: `class="htmx-indicator"` — htmx adds `htmx-request` class during requests, which can toggle display via CSS. Study how existing fragments handle loading states.

### 3. templates/fragments/code_module_detail.html

This fragment renders the Level 2 module view. It replaces `#code-detail-panel`.

Context variables:
- `project_id: str`
- `module: dict` — the module entry (`name`, `path`, `slug`, `description`)
- `doc_html: str | None` — **pre-rendered HTML** from the Level 2 doc's markdown content (rendered server-side by S03 via `markdown.markdown(...)`); `None` when `generating=True`
- `was_cached: bool`
- `generating: bool`

Do NOT receive the raw `ProjectDoc` object or raw markdown — all markdown-to-HTML conversion happens in the router (S03) before rendering. This is mandatory: rendering `doc.content | safe` directly with raw markdown is both an XSS risk AND produces incorrect output (markdown doesn't render as HTML).

```html
<!-- Level 2 Module Detail View -->
<!-- Rendered when hx-get="/api/projects/{project_id}/code/modules/{module_slug}" responds -->

{% if generating %}
  <!-- Polling state: generation in progress -->
  <div
    hx-get="/api/projects/{{ project_id }}/code/modules/{{ module.slug }}"
    hx-trigger="load delay:2s"
    hx-target="#code-detail-panel"
    hx-swap="innerHTML"
  >
    <div class="flex items-center gap-2 py-8">
      <svg class="animate-spin h-5 w-5 text-blue-500" ...></svg>
      <span class="text-gray-600">Generating module analysis for {{ module.name }}...</span>
    </div>
  </div>

{% else %}
  <!-- Breadcrumb -->
  <nav class="flex items-center gap-2 text-sm text-gray-500 mb-4">
    <button
      hx-get="/api/projects/{{ project_id }}/code/modules"
      hx-target="#code-detail-panel"
      hx-swap="innerHTML"
      class="hover:text-blue-600"
    >Architecture</button>
    <span>›</span>
    <span class="text-gray-800 font-medium">{{ module.path }}</span>
  </nav>

  <!-- Header -->
  <div class="flex items-center justify-between mb-4">
    <h2 class="text-lg font-semibold">{{ module.name }}</h2>
    <div class="flex items-center gap-3">
      {% if not was_cached %}
        <span class="text-xs text-green-600 bg-green-50 px-2 py-1 rounded">freshly generated</span>
      {% else %}
        <span class="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">cached</span>
      {% endif %}
      <button
        class="text-sm text-gray-600 hover:text-blue-600 flex items-center gap-1"
        hx-post="/api/projects/{{ project_id }}/code/modules/{{ module.slug }}/generate"
        hx-target="#code-detail-panel"
        hx-swap="innerHTML"
        hx-indicator="#code-loading-spinner"
      >
        ↻ Regenerate
      </button>
    </div>
  </div>

  <!-- Pre-rendered HTML content (converted server-side from markdown) -->
  <div class="prose prose-sm max-w-none">
    {{ doc_html | safe }}
  </div>
{% endif %}
```

**Important**: `doc_html` is already sanitized HTML rendered by S03's router. The `| safe` filter is appropriate here because the conversion happened server-side using the `markdown` Python package. Do NOT pass raw markdown through `| safe`.

### 4. templates/fragments/code_symbol_panel.html

This fragment renders inline below a file row when the [explain] button is clicked. It does NOT replace any existing content — it is inserted via `hx-swap="afterend"`.

Context variables:
- `explanation_html: str` — **pre-rendered HTML** (the router calls `markdown.markdown(llm_response)`)
- `file_path: str`
- `symbol_name: str | None`

```html
<!-- Level 3 Inline Symbol Panel -->
<!-- Inserted via hx-swap="afterend" below the file row -->
<div
  id="symbol-panel-{{ file_path | replace('/', '-') | replace('.', '-') }}"
  class="my-2 p-4 border border-blue-200 rounded-lg bg-blue-50"
>
  <div class="flex items-start justify-between">
    <div class="font-mono text-sm font-semibold text-blue-800">
      {% if symbol_name %}{{ symbol_name }}{% else %}{{ file_path }}{% endif %}
    </div>
    <button
      class="text-gray-400 hover:text-gray-600 text-lg leading-none"
      onclick="this.closest('[id^=symbol-panel-]').remove()"
      title="Close"
    >✕</button>
  </div>
  <div class="prose prose-sm mt-2 max-w-none">
    {{ explanation_html | safe }}
  </div>
</div>
```

The close button uses a minimal inline JS `onclick` to remove the panel — this is acceptable per the project's pattern of using htmx + minimal vanilla JS.

### 5. Modifications to the Architecture View (Code tab)

Find the existing Code tab template that renders the Level 1 architecture view (Mermaid diagram + text). Add:

a) **COMPONENTS section**: A container `<div id="code-components-section">` below the Mermaid diagram, loaded via htmx on page load:

```html
<div
  id="code-components-section"
  hx-get="/api/projects/{{ project.id }}/code/modules"
  hx-trigger="load"
  hx-swap="innerHTML"
>
  <!-- Loaded via htmx after page renders -->
</div>
```

b) **Detail panel**: A container for Level 2/3 content, initially empty:

```html
<div id="code-detail-panel" class="mt-6">
  <!-- Level 2 and Level 3 views load here via htmx -->
</div>
```

c) **Loading spinner**: The htmx indicator element:

```html
<div id="code-loading-spinner" class="htmx-indicator hidden">
  {% include "fragments/code_module_spinner.html" %}
</div>
```

The file to modify is `dashboard/templates/fragments/code_architecture_view.html` (created by F-00047). Add the three containers (`#code-components-section`, `#code-detail-panel`, `#code-loading-spinner`) below the Mermaid diagram inside that fragment — do NOT touch `project_code.html`.

### 6. [explain] Buttons for File Rows

In `code_module_detail.html`, where file rows are rendered, each row needs an [explain] button. If the Level 2 API returns a structured file list (not just markdown), render explicit file rows. Each row:

```html
<div class="flex items-center justify-between py-2 border-b border-gray-100">
  <div class="flex items-center gap-3">
    <span class="font-mono text-sm">{{ file.path }}</span>
    <span class="text-sm text-gray-500">{{ file.description }}</span>
  </div>
  <button
    class="text-xs text-blue-600 hover:text-blue-800 px-2 py-1 border border-blue-200 rounded"
    hx-get="/api/projects/{{ project_id }}/code/symbol?file_path={{ file.path | urlencode }}"
    hx-target="closest div"
    hx-swap="afterend"
  >
    explain
  </button>
</div>
```

If only markdown content is available (no structured file list), skip the explicit file rows — the [explain] buttons require knowing the file paths. In that case, note this limitation in your report and implement what is possible.

### 7. Breadcrumb in Level 3 View

When a symbol panel opens (Level 3), update the breadcrumb in the Level 2 view to show:
```
Architecture > engine/ > ring.h
```

Since Level 3 is rendered inline (not replacing the Level 2 view), the breadcrumb update requires either:
a) An htmx `hx-target` pointing to the breadcrumb element + `hx-swap="innerHTML"` to update it, or
b) A small vanilla JS function triggered after the symbol panel inserts.

Prefer option (a) if feasible. If the symbol panel is loaded via `hx-swap="afterend"` on the file row, the breadcrumb update can be done via `hx-swap-oob` on a secondary element returned in the same response. Study if the API returns a response that includes both the panel content and an OOB breadcrumb update.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md` for:
- Fragment templates must NOT extend `base.html`
- Tailwind via CDN — no dynamic class construction
- htmx for all server interactions — no fetch()/XHR in JS
- Accessibility: use semantic HTML (`<button>` not `<div onclick>`), proper ARIA labels on interactive elements
- Naming: fragment files use snake_case, `code_` prefix for this feature's fragments
- Jinja2 template variables use snake_case

## Test Verification

This step has no automated frontend tests (no Jest/Vitest in the project). Verification is done by:

1. Run `uv run pytest tests/unit/ -v` — no regressions
2. Run `uv run pytest tests/integration/ -v` — no regressions
3. Start the dashboard: `make dashboard-start`
4. Use playwright-cli to verify the UI renders correctly:
   ```bash
   playwright-cli kill-all
   playwright-cli open http://localhost:9900
   playwright-cli snapshot
   playwright-cli screenshot
   ```
5. Navigate to a project's Code tab and verify:
   - Module cards appear below the Mermaid diagram after page load
   - Clicking "View details" loads Level 2 view in the detail panel
   - Breadcrumb shows "Architecture > {module_path}"
   - [explain] buttons load inline symbol panels
   - Close button removes symbol panel
   - Regenerate button triggers force regeneration

If browser verification is not possible in your environment (headless WSL), note this in your report and provide the template output instead.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "F-00048",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/code_module_cards.html",
    "dashboard/templates/fragments/code_module_detail.html",
    "dashboard/templates/fragments/code_symbol_panel.html",
    "dashboard/templates/fragments/code_module_spinner.html",
    "dashboard/templates/fragments/code_architecture_view.html"
  ],
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
