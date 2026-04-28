# F-00065_S03_Frontend_prompt

**Work Item**: F-00065 — Diagram display in code view
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00065/F-00065_Feature_Design.md`
- `ai-dev/active/F-00065/reports/F-00065_S01_API_report.md`
- `dashboard/templates/fragments/code_module_detail.html`
- `dashboard/templates/fragments/code_architecture_view.html`
- `dashboard/routers/code_ui.py`
- `dashboard/static/chat/mermaid.js`
- `dashboard/templates/project_code.html`

## Output Files

- `ai-dev/active/F-00065/reports/F-00065_S03_Frontend_report.md`
- `dashboard/templates/fragments/code_module_diagram.html` (new)
- `dashboard/templates/fragments/code_architecture_diagram.html` (new)
- `dashboard/templates/fragments/code_module_detail.html` (modified)
- `dashboard/templates/fragments/code_architecture_view.html` (modified)
- `dashboard/routers/code_ui.py` (modified — fix _preprocess_mermaid)

## Context

You are implementing the frontend for **F-00065: Diagram display in code view**.

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Key constraints:
- Fragment templates MUST NOT extend `base.html`
- CSS is prebuilt via `make css` — run it after template changes that introduce new Tailwind classes
- `window.iwChat.upgradeMermaidBlock(preEl)` and `window.iwChat.upgradeAllMermaidBlocks(container)` are the brand-themed Mermaid renderers (ELK + handDrawn + brand CSS vars) defined in `dashboard/static/chat/mermaid.js`
- These functions look for `pre[data-lang="mermaid"]` elements

## Requirements

### 1. Fix `dashboard/routers/code_ui.py` — `_preprocess_mermaid`

**Current (broken)**: `_preprocess_mermaid` (line ~61) converts ` ```mermaid ... ``` ` to `<div class="mermaid">...</div>`. This never renders because `chat/mermaid.js` sets `startOnLoad: false` globally.

**Fix**: Change the `pattern.sub` replacement to output `<pre data-lang="mermaid"><code>\1</code></pre>` instead. This function has exactly one caller (`_render_architecture_html`, same file) — no parameter change needed, no other callers to worry about.

### 2. New fragment: `dashboard/templates/fragments/code_module_diagram.html`

```html
<!-- Receives: project_id, slug, diagram_dsl (str|None) -->
<div id="code-module-diagram-{{ slug }}" class="code-module-diagram mt-4">
  {% if diagram_dsl %}
  <div class="px-4 pb-2">
    <h4 class="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Component Diagram</h4>
    <div class="code-diagram-container">
      <pre data-lang="mermaid"><code>{{ diagram_dsl | e }}</code></pre>
    </div>
  </div>
  {% else %}
  <div class="code-diagram-empty px-4 pb-2 text-xs text-muted-foreground italic">
    No diagram yet — run "Generate Code Map" to create one.
  </div>
  {% endif %}
</div>
<script>
(function () {
  var container = document.getElementById('code-module-diagram-{{ slug }}');
  if (!container || typeof window.iwChat === 'undefined') return;
  if (window.iwChat.upgradeAllMermaidBlocks) {
    window.iwChat.upgradeAllMermaidBlocks(container);
  }
})();
</script>
```

**Important**: The `{{ diagram_dsl | e }}` must HTML-escape the DSL — it is raw Mermaid text, not trusted HTML.

### 3. Updated fragment: `dashboard/templates/fragments/code_module_detail.html`

After the `{% elif doc_html %}` block that renders the module documentation, add an htmx-loaded diagram section:

```html
{% if doc_html %}
  <!-- Diagram section — loads after doc -->
  <div id="code-module-diagram-slot"
       hx-get="/api/projects/{{ project_id }}/code/modules/{{ module.slug }}/diagram"
       hx-trigger="load"
       hx-swap="innerHTML">
  </div>
{% endif %}
```

Place this after the `<div class="prose-doc text-sm">{{ doc_html | safe }}</div>` block and before the closing `</div>` of the `p-4` section.

### 4. New fragment: `dashboard/templates/fragments/code_architecture_diagram.html`

```html
<!-- Receives: project_id, arch_diagram_dsl (str|None) -->
{% if arch_diagram_dsl %}
<div id="code-arch-diagram" class="mt-4 border-t border-border pt-4">
  <div class="px-4 pb-2">
    <h3 class="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Architecture Diagram</h3>
    <div class="code-diagram-container">
      <pre data-lang="mermaid"><code>{{ arch_diagram_dsl | e }}</code></pre>
    </div>
  </div>
</div>
<script>
(function () {
  var container = document.getElementById('code-arch-diagram');
  if (!container || typeof window.iwChat === 'undefined') return;
  if (window.iwChat.upgradeAllMermaidBlocks) {
    window.iwChat.upgradeAllMermaidBlocks(container);
  }
})();
</script>
{% endif %}
```

### 5. Updated fragment: `dashboard/templates/fragments/code_architecture_view.html`

Add at the bottom of the fragment (after `#code-components-section` and `#code-detail-panel`):

```html
{% if arch_diagram_dsl %}
  {% include "fragments/code_architecture_diagram.html" %}
{% endif %}
```

Also update the existing inline `<style>` block: remove the `.prose-doc .mermaid { ... }` rule (obsolete after the `_preprocess_mermaid` fix — `<div class="mermaid">` blocks no longer exist). Replace with nothing (CSS for the new `<pre data-lang="mermaid">` is handled by `upgradeAllMermaidBlocks`).

### 6. Run `make css`

After all template changes, run:
```bash
make css
```
This rebuilds `dashboard/static/styles.css`. Commit the updated CSS file.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — must pass
2. `make typecheck` — zero errors on touched files
3. `make lint` — zero errors

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "F-00065",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/code_ui.py",
    "dashboard/templates/fragments/code_module_diagram.html",
    "dashboard/templates/fragments/code_architecture_diagram.html",
    "dashboard/templates/fragments/code_module_detail.html",
    "dashboard/templates/fragments/code_architecture_view.html",
    "dashboard/static/styles.css"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
