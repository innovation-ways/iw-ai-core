# F-00047 S03 — Frontend: Code Tab Templates + Job UI

## Mission

Implement all Jinja2 templates for the Code Understanding tab, wire up htmx interactions, implement the SSE EventSource client in vanilla JS, add Mermaid.js to the base template, and add the "Code" nav link to the sidebar.

## IMPORTANT: Read Existing Patterns First

Before writing a single line of HTML, you MUST read these files to understand existing conventions:

1. `CLAUDE.md` — architecture rules
2. `dashboard/CLAUDE.md` — template rules (fragments must NOT extend base.html; Tailwind CDN only; no dynamic class construction)
3. `dashboard/templates/base.html` — understand the full layout, existing CDN scripts, `{% block head %}` and `{% block scripts %}`
4. `dashboard/templates/fragments/nav_projects.html` — exact pattern for the sidebar nav link list you will modify
5. `dashboard/templates/fragments/docs_job_status.html` — SSE/job status fragment pattern to follow
6. `dashboard/templates/docs_detail.html` — tab strip pattern, how markdown content is rendered, how generate buttons work
7. `dashboard/templates/docs_library.html` — page-level layout pattern (header + action buttons)
8. `dashboard/routers/code_ui.py` — the routes and template context variables that S01 implemented
9. `ai-dev/active/F-00047/F-00047_Feature_Design.md` — full UI specification and wireframes

## What to Implement

### 1. Modify `dashboard/templates/base.html`

Add Mermaid.js CDN script. Check if it is already present before adding. Place it after the `marked.js` script tag:

```html
<!-- Mermaid.js for code architecture diagrams -->
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<script>
  document.addEventListener('DOMContentLoaded', function() {
    if (typeof mermaid !== 'undefined') {
      mermaid.initialize({ startOnLoad: true, theme: 'default' });
    }
  });
</script>
```

Also add a global htmx:afterSwap listener that re-initializes Mermaid diagrams injected by htmx swaps. Place in the `{% block scripts %}` area of base.html or in the inline `<script>` block at the bottom of base.html:

```javascript
document.body.addEventListener('htmx:afterSwap', function(e) {
  if (typeof mermaid !== 'undefined' && e.detail.target) {
    var nodes = e.detail.target.querySelectorAll('.mermaid:not([data-processed])');
    if (nodes.length > 0) {
      mermaid.init(undefined, nodes);
    }
  }
});
```

### 2. Modify `dashboard/templates/fragments/nav_projects.html`

Add "Code" to the existing links list. The list currently ends with `('/project/' ~ project.id ~ '/research', 'Research')`. Append after Research:

```jinja2
('/project/' ~ project.id ~ '/code', 'Code'),
```

Match the exact Jinja2 list format already in the file. The active-link highlighting logic already handles path prefix matching, so no additional changes are needed.

### 3. Create `dashboard/templates/project_code.html`

This file MUST extend `base.html`. Study `docs_library.html` for the standard page layout.

Template context variables (provided by `code_ui.py` route handler — these field names are final, do NOT invent alternates):
- `current_project` — Project ORM object
- `index_status` — dict or None:
  ```
  {
    "provider": str,
    "llm_model": str,                   # not "chat_model"
    "embed_model": str,
    "last_indexed_at": datetime | None,
    "files_count": int,
    "chunks_count": int,
    "languages_detected": list[str],    # not "languages_json"
    "level1_doc_markdown": str | None,  # resolved by the route handler from ProjectDoc.content
  }
  ```
- `running_job` — CodeIndexJob ORM object or None
- `last_completed_job` — CodeIndexJob ORM object or None
- `last_completed_recent` — bool (computed in route, replaces the previous `completed_recently` model attribute)
- `last_completed_duration` — str | None, e.g. `"4m 32s"` (computed in route, replaces the previous `duration_formatted` model attribute)
- `arch_doc` — ProjectDoc ORM object or None (for the architecture fragment include)
- `content_html` — str | None — pre-rendered architecture HTML with Mermaid blocks replaced. Used by the architecture panel include. Guard `{% if content_html %}` to decide between architecture view vs empty state; do NOT guard on `index_status.level1_doc_markdown` (that raw markdown is not usable by the fragment).

Layout structure:
```
{% extends "base.html" %}
{% block title %}Code — {{ current_project.display_name }}{% endblock %}
{% block content %}

  <!-- Page Header -->
  <div class="mb-6 flex items-start justify-between">
    <div>
      <h1 class="text-2xl font-semibold text-foreground">Code Understanding</h1>
      <!-- meta bar: provider · models · last indexed · file/chunk counts -->
      {% if index_status %}
      <p class="text-muted-foreground text-sm mt-1">
        Provider: {{ index_status.provider }} · {{ index_status.llm_model }} · {{ index_status.embed_model }}
        · Last indexed: {{ index_status.last_indexed_at | timeago }} · {{ index_status.files_count }} files · {{ index_status.chunks_count | intcomma }} chunks
      </p>
      {% endif %}
    </div>

    <!-- Dropdown action button (right side) -->
    <div> ... Generate Code Map dropdown ... </div>
  </div>

  <!-- Job status panel (live updates) -->
  <div id="code-status-panel" class="mb-4">
    {% if running_job %}
      {% include "fragments/code_job_status.html" %}
    {% elif last_completed_job and last_completed_recent %}
      {% include "fragments/code_job_report.html" %}
    {% endif %}
  </div>

  <!-- Architecture panel -->
  <div id="code-architecture-panel">
    {% if content_html %}
      {% include "fragments/code_architecture_view.html" %}
    {% else %}
      {% include "fragments/code_empty_state.html" %}
    {% endif %}
  </div>

{% endblock %}
```

#### Dropdown Button

Implement the "Generate Code Map" dropdown using pure CSS/JS. No framework. Use a `<div class="relative">` wrapper with a positioned menu div. The dropdown menu contains three `<button>` elements wired with `hx-post`:

- "Generate Code Map" → `hx-post="/project/{{ current_project.id }}/api/code/index"`
- "Re-index changed files" → `hx-post="/project/{{ current_project.id }}/api/code/reindex"`
- "Regenerate Map" → `hx-post="/project/{{ current_project.id }}/api/code/regen-map"`

All three POST buttons must:
- `hx-target="#code-status-panel"` — replace the status panel with the returned fragment
- `hx-swap="innerHTML"`
- Show loading state: add `disabled` and a spinner class on click (use `hx-indicator` or `htmx:beforeRequest` event)
- Close the dropdown after click

Dropdown toggle JS:
```javascript
function toggleCodeDropdown() {
  var menu = document.getElementById('code-dropdown-menu');
  menu.classList.toggle('hidden');
}
// Close on outside click
document.addEventListener('click', function(e) {
  if (!e.target.closest('#code-action-dropdown')) {
    var menu = document.getElementById('code-dropdown-menu');
    if (menu) menu.classList.add('hidden');
  }
});
```

#### Button Loading State

When any POST button is clicked, disable it and the other dropdown buttons until the response arrives. Use the `htmx:beforeRequest` and `htmx:afterRequest` events:

```javascript
document.body.addEventListener('htmx:beforeRequest', function(e) {
  if (e.detail.elt.closest('#code-action-dropdown')) {
    document.querySelectorAll('#code-action-dropdown button').forEach(function(b) {
      b.disabled = true;
      b.classList.add('opacity-60', 'cursor-not-allowed');
    });
  }
});
document.body.addEventListener('htmx:afterRequest', function(e) {
  if (e.detail.elt.closest('#code-action-dropdown')) {
    document.querySelectorAll('#code-action-dropdown button').forEach(function(b) {
      b.disabled = false;
      b.classList.remove('opacity-60', 'cursor-not-allowed');
    });
  }
});
```

### 4. Create `dashboard/templates/fragments/code_job_status.html`

This file must NOT extend `base.html`.

Context variables needed: `running_job` (CodeIndexJob ORM object), `current_project` (Project ORM object).

Layout:
- Container `div` with id `code-job-status-panel`
- Top row: spinner SVG (use same animate-spin spinner as in `docs_job_status.html`) + label "Indexing in progress..." (or phase-specific: "Embedding...", "Generating map...")
- Second row: phase badge + elapsed timer
- Third row: "Files: X / Y indexed" + "Chunks: Z"
- Progress bar: `<div class="w-full bg-muted rounded-full h-2"><div id="code-progress-bar" class="h-full bg-primary rounded-full" style="width: 0%"></div></div>`
- Bottom row: elapsed time (`id="code-elapsed-time"`) + Cancel button:
  - `hx-delete="/project/{{ current_project.id }}/api/code/index"`
  - `hx-target="#code-status-panel"`
  - `hx-swap="innerHTML"`
  - `hx-confirm="Cancel the running code index job?"`
  - On click the button becomes disabled and swaps its label to "Cancelling..." until the htmx response arrives. The SSE stream's terminal `{"event":"done","status":"cancelled"}` event then triggers the usual full-panel refresh (same code path as `completed`/`failed`).

SSE EventSource in vanilla JS (NOT htmx hx-ext="sse"):

```javascript
(function() {
  var projectId = '{{ current_project.id }}';
  var streamUrl = '/project/' + projectId + '/api/code/index/stream';
  var es = new EventSource(streamUrl);

  function updateUI(data) {
    // Phase label
    var phaseEl = document.getElementById('code-phase-label');
    if (phaseEl && data.phase) {
      var phaseLabels = {
        'indexing': 'Indexing files...',
        'embedding': 'Creating embeddings...',
        'map_generation': 'Generating architecture map...',
      };
      phaseEl.textContent = phaseLabels[data.phase] || data.phase;
    }
    // Files progress
    var filesEl = document.getElementById('code-files-progress');
    if (filesEl && data.files_total) {
      filesEl.textContent = data.files_indexed + ' / ' + data.files_total + ' indexed';
    }
    // Chunks
    var chunksEl = document.getElementById('code-chunks-count');
    if (chunksEl && data.chunks_created !== undefined) {
      chunksEl.textContent = data.chunks_created.toLocaleString();
    }
    // Progress bar
    var bar = document.getElementById('code-progress-bar');
    if (bar && data.files_total) {
      var pct = Math.round((data.files_indexed / data.files_total) * 100);
      bar.style.width = pct + '%';
    }
  }

  es.onmessage = function(e) {
    try {
      var data = JSON.parse(e.data);
      if (data.event === 'progress') {
        updateUI(data);
      } else if (data.event === 'done') {
        // Terminal statuses: completed | failed | cancelled | idle
        es.close();
        // Refresh both panels via htmx
        htmx.ajax('GET', '/project/' + projectId + '/api/code/status',
                  {target: '#code-status-panel', swap: 'innerHTML'});
        htmx.ajax('GET', '/project/' + projectId + '/api/code/architecture',
                  {target: '#code-architecture-panel', swap: 'innerHTML'});
      }
    } catch (err) { /* ignore parse errors */ }
  };

  es.onerror = function() {
    es.close();
  };

  // Elapsed timer
  var startTime = Date.now();
  var timerId = setInterval(function() {
    var el = document.getElementById('code-elapsed-time');
    if (!el) { clearInterval(timerId); return; }
    var elapsed = Math.floor((Date.now() - startTime) / 1000);
    var mins = Math.floor(elapsed / 60);
    var secs = elapsed % 60;
    el.textContent = mins + ':' + (secs < 10 ? '0' : '') + secs + ' elapsed';
  }, 1000);
})();
```

### 5. Create `dashboard/templates/fragments/code_empty_state.html`

This file must NOT extend `base.html`.

Context variables needed: `index_status` (may be None), `current_project`. Use `index_status.llm_model` (NOT `chat_model`) for provider/model display.

Layout (centered, vertically padded):
```
<div class="flex flex-col items-center justify-center py-20 text-center bg-card border border-border rounded-lg">
  <!-- SVG icon: code/terminal brackets -->
  <svg ...><!-- terminal/code icon --></svg>
  <h3 class="text-lg font-semibold text-foreground mb-2">No code map generated yet.</h3>
  {% if index_status %}
  <p class="text-sm text-muted-foreground mb-4">
    Provider: {{ index_status.provider }} · {{ index_status.llm_model }}
  </p>
  {% else %}
  <p class="text-sm text-muted-foreground mb-4">
    Configure code understanding in project settings to get started.
  </p>
  {% endif %}
  <button hx-post="/project/{{ current_project.id }}/api/code/index"
          hx-target="#code-status-panel"
          hx-swap="innerHTML"
          class="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 transition-opacity">
    <svg class="w-4 h-4"><!-- lightning bolt --></svg>
    Generate Code Map
  </button>
</div>
```

Use the same SVG icons pattern seen in `docs_detail.html` (stroke-based, `fill="none"`).

### 6. Create `dashboard/templates/fragments/code_architecture_view.html`

This file must NOT extend `base.html`.

Context variables needed:
- `content_html` — pre-processed HTML string with Mermaid blocks replaced by `<div class="mermaid">...</div>` (server-side pre-processing done in the route handler from `ProjectDoc.content`)
- `arch_doc` — the `ProjectDoc` ORM object (may be None)
- `current_project`

Layout:
```html
<div class="bg-card border border-border rounded-lg overflow-hidden">
  <div class="px-4 py-2 border-b border-border">
    <h2 class="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Architecture</h2>
  </div>
  <div class="p-8 overflow-y-auto" style="max-height: calc(100vh - 280px);">
    <div class="prose-doc max-w-4xl mx-auto">
      <!-- Reuse the same .prose-doc styles already defined in docs_detail.html -->
      <!-- Add Mermaid-specific styles -->
      <style>
        .mermaid { margin: 1.5em 0; text-align: center; }
        .mermaid svg { max-width: 100%; height: auto; }
      </style>
      {{ content_html | safe }}
    </div>
  </div>
</div>
```

The `.prose-doc` CSS is already global (defined inline in `docs_detail.html` — replicate the same `<style>` block here since fragments don't share page CSS).

### 7. Create `dashboard/templates/fragments/code_job_report.html`

This file must NOT extend `base.html`.

Context variables needed: `last_completed_job` (CodeIndexJob ORM object), `last_completed_duration` (str | None, computed in the route handler).

Layout (success panel):
```html
<div class="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
  <div class="flex items-center gap-2 mb-2">
    <svg class="w-5 h-5 text-green-600 dark:text-green-400"><!-- checkmark --></svg>
    <span class="font-medium text-green-700 dark:text-green-300">Code map generated successfully</span>
  </div>
  <div class="text-sm text-green-700 dark:text-green-300 space-y-1">
    {% if last_completed_duration %}
    <p>Duration: {{ last_completed_duration }}</p>
    {% endif %}
    <p>Files indexed: {{ last_completed_job.files_indexed }}  ·  Chunks: {{ last_completed_job.chunks_created | intcomma }}</p>
    {% if last_completed_job.languages_detected %}
    <p>Languages: {{ last_completed_job.languages_detected | join(", ") }}</p>
    {% endif %}
    {% if last_completed_job.llm_model %}
    <p>Model: {{ last_completed_job.llm_model }} · Embed: {{ last_completed_job.embed_model }}</p>
    {% endif %}
  </div>
</div>
```

**Field names**: this fragment must use ONLY the F-00045 column names as they exist in `orch/db/models.py`: `files_indexed`, `chunks_created`, `languages_detected` (JSONB list), `llm_model`, `embed_model`. Do NOT use `chat_model`, `languages_json`, `duration_formatted`, or `completed_recently` — these do not exist on the model. The duration string comes from `last_completed_duration` in the template context (computed by the route handler). Read `orch/db/models.py` to confirm before writing this template.

## Styling Rules

- Use Tailwind utility classes only — NO inline styles except for dynamic values (progress bar width, max-height)
- Do NOT construct dynamic class strings (e.g., no `"text-" + color` concatenation)
- All dark mode variants must use `dark:` prefix classes
- Follow the color token pattern: `bg-card`, `border-border`, `text-foreground`, `text-muted-foreground`, `bg-primary`, `text-primary-foreground`, etc. — same tokens used throughout the existing templates

## Accessibility

- All interactive elements must have `aria-label` where label text is not visible
- Progress bar: add `role="progressbar"` with `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`
- Dropdown menu: add `aria-expanded` on the toggle button, `role="menu"` on the menu div
- Spinner: add `aria-label="Loading"` and `role="status"` on the spinner container

## Quality Gates

After implementation, run:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy orch/ dashboard/
uv run pytest tests/unit/ -v
```

Then do a browser verification using playwright-cli:
```bash
playwright-cli kill-all
playwright-cli open http://localhost:9900/project/{a-real-project-id}/code
playwright-cli snapshot   # verify Code tab renders
playwright-cli screenshot  # capture the page state
```

All must pass/succeed before marking this step done.
