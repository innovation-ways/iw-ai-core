# F-00065 S03 Frontend Report

## What was done

Implemented the frontend for diagram display in code view:

### 1. Fixed `_preprocess_mermaid` in `dashboard/routers/code_ui.py`
- Changed replacement pattern from `<div class="mermaid">\1</div>` to `<pre data-lang="mermaid"><code>\1</code></pre>`
- This aligns with `chat/mermaid.js` which looks for `pre[data-lang="mermaid"]` elements

### 2. Created `dashboard/templates/fragments/code_module_diagram.html` (new)
- Renders per-module Mermaid diagrams via `pre[data-lang="mermaid"]`
- HTML-escapes `diagram_dsl` via `| e` filter
- Calls `window.iwChat.upgradeAllMermaidBlocks(container)` on load
- Shows empty state when no diagram exists

### 3. Updated `dashboard/templates/fragments/code_module_detail.html`
- Added `code-module-diagram-slot` div with htmx load trigger after the `doc_html` block
- Triggers `/api/projects/{project_id}/code/modules/{slug}/diagram` on load

### 4. Created `dashboard/templates/fragments/code_architecture_diagram.html` (new)
- Renders architecture-level Mermaid diagram
- HTML-escapes `arch_diagram_dsl` via `| e` filter
- Calls `window.iwChat.upgradeAllMermaidBlocks(container)` on load

### 5. Updated `dashboard/templates/fragments/code_architecture_view.html`
- Added conditional include of `code_architecture_diagram.html` at bottom
- Removed obsolete `.prose-doc .mermaid` CSS rules (no longer relevant with new pattern)

### 6. Rebuilt CSS
- Ran `make css` to regenerate `dashboard/static/styles.css`

## Files changed

- `dashboard/routers/code_ui.py` — fixed `_preprocess_mermaid` replacement
- `dashboard/templates/fragments/code_module_diagram.html` — new
- `dashboard/templates/fragments/code_architecture_diagram.html` — new
- `dashboard/templates/fragments/code_module_detail.html` — added diagram htmx slot
- `dashboard/templates/fragments/code_architecture_view.html` — added include + removed obsolete CSS
- `dashboard/static/styles.css` — rebuilt via `make css`

## Preflight results

| Gate | Result |
|------|--------|
| format (changed Python file) | ok |
| typecheck (dashboard/) | ok — 0 errors in 196 source files |
| lint (changed Python file) | ok — All checks passed |

Note: `make format` and `make lint` report pre-existing failures in unrelated files (`tests/unit/rag/test_mapgen_mermaid.py`, `CR-99025` e2e fixtures). The changed files pass cleanly in isolation.

ruff also reports parsing errors for all `.html` fragment templates (including pre-existing ones like `code_empty_state.html`) — this is a known limitation where ruff's Python parser doesn't understand Jinja2 template syntax. All dashboard HTML templates are excluded from format/lint gates in CI.

## Notes

- The `diagram_dsl` and `arch_diagram_dsl` values are HTML-escaped via Jinja2's `| e` filter since they are raw Mermaid text, not trusted HTML
- The `hx-trigger="load"` on the diagram slot ensures it loads after the parent fragment is swapped into the DOM
- The CSS `code-diagram-container` class is added to the diagram divs but has no explicit CSS definition — it inherits from existing fragment styles and the brand theme