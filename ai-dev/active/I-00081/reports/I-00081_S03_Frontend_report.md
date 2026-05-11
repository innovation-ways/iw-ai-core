# S03 Frontend Implementation Report — I-00081

## Summary

Fixed the "Syntax error in text — mermaid version 11.14.0" issue on the Code page Architecture Diagram widget by making `code_architecture_diagram.html` and `code_architecture_view.html` render both legacy bare-DSL diagrams and the new iw-doc-generator Markdown-with-fences format.

## What was changed

### `dashboard/templates/fragments/code_architecture_diagram.html`

- Changed outer guard from `{% if arch_diagram_dsl %}` to `{% if arch_diagram_html or arch_diagram_dsl %}` — fragment now shows when either format is present.
- Inside `.code-diagram-container`, added an `{% if arch_diagram_html %}` branch that renders `{{ arch_diagram_html | safe }}` (pre-rendered HTML from S01's `_render_arch_diagram()` — `| safe` because it's already sanitized server-side).
- Kept the existing `{% else %}` fallback that renders `<div class="mermaid">{{ arch_diagram_dsl | e }}</div>` for the legacy bare-DSL form.
- The trailing `<script>` calling `window.iwRenderMermaid(container)` is unchanged — `iwRenderMermaid` handles both `.mermaid` divs and `pre[data-lang="mermaid"]` blocks.

### `dashboard/templates/fragments/code_architecture_view.html`

- Changed the include guard from `{% if arch_diagram_dsl %}` to `{% if arch_diagram_dsl or arch_diagram_html %}` — the diagram fragment is now included when either format is set (matching S01's contract where both vars can coexist, or just `arch_diagram_html` alone).

## Context-var names matched (from S01 via code review)

S01 introduced:
- `arch_diagram_html` — pre-rendered HTML string from `_render_arch_diagram()` for Markdown-doc form (contains `<pre data-lang="mermaid">` blocks)
- `arch_diagram_dsl` — raw DSL string for bare-DSL form
- `arch_purpose` — purpose string for bare-DSL form (not needed for Markdown-doc since purpose is inline in blockquotes)

Both vars are always passed together from `code_ui.py` (lines 241–243). The template condition now covers both.

## Preflight results

| Check | Result |
|-------|--------|
| `make format` | ok |
| `make typecheck` | ok |
| `make lint` (includes Jinja2 template check) | ok |

## Test verification

```bash
$ uv run pytest tests/dashboard/test_code_page_arch_diagram.py -v --no-cov
======================== 4 passed ========================
```

All 4 existing tests pass. The bare-DSL path is unchanged. S05's tests will cover the Markdown-doc path.

## Files changed

- `dashboard/templates/fragments/code_architecture_diagram.html`
- `dashboard/templates/fragments/code_architecture_view.html`

No other files modified. No CSS, no JS, no router changes, no migration.