# I-00081 S01 Backend Implementation Report

## Summary

Implemented `_render_arch_diagram` in `dashboard/routers/code_ui.py` — a format-aware helper that branches on whether the stored `diagram-architecture` doc is a Markdown-with-fences document (iw-doc-generator) or bare Mermaid DSL (mapgen). Wired `arch_diagram_html` into both `code_page` and `code_architecture` route contexts.

**Key finding**: The helper itself is correct (unit tests confirm correct HTML output). The route-level integration tests for Markdown format fail because the template that renders `arch_diagram_html` is S03's job — `code_architecture_view.html` currently only includes `code_architecture_diagram.html` when `arch_diagram_dsl` is set, so `arch_diagram_html` isn't rendered yet.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/code_ui.py` | Added `_render_arch_diagram()` helper; wired `arch_diagram_html` into `code_page` (line 224) and `code_architecture` (line 356) route contexts |
| `tests/dashboard/test_i00081_code_page_arch_diagram.py` | New test file: 2 unit tests + 3 route tests; S05 will own/maintain this |

## What Was Implemented

### `_render_arch_diagram(raw: str) -> tuple[str | None, str | None, str | None]`

**Returns (rendered_html, arch_diagram_dsl, arch_purpose):**

1. **Markdown-doc form** (detected by `^```mermaid` at line-start after comment stripping):
   - Strips HTML comments (`<!--.*?-->`)
   - Drops a single leading `# …` H1 line (duplicates the widget's own `<h3>`)
   - Strips `---\nconfig:\n  layout: elk\n---` ELK front-matter from each fenced block
   - Runs through `_preprocess_mermaid` + `render_markdown`
   - Returns `(rendered_html, None, None)`

2. **Bare-DSL form** (no fenced block):
   - Calls existing `_clean_diagram_dsl(raw)` to strip comments + ELK front-matter
   - Extracts `<!-- purpose: … -->` from the raw string (not stripped)
   - Returns `(None, cleaned_dsl, purpose)`

### Route Changes

- `code_page()`: Replaced the old `<!-- purpose: -->` regex + `_clean_diagram_dsl` block with `arch_diagram_html, arch_diagram_dsl, arch_purpose = _render_arch_diagram(arch_diagram_doc.content)`. Added `arch_diagram_html` to template context.

- `code_architecture()` (htmx fragment): Same replacement. Added `arch_diagram_html` to template context.

### Approach

**Two separate context variables** (not folded into one):
- `arch_diagram_html` — set when Markdown-doc form detected; S03 will render it
- `arch_diagram_dsl` — set when bare-DSL form detected; existing template path renders it
- `arch_purpose` — set for bare-DSL; None for Markdown-doc (purpose conveyed inline by blockquotes)

This avoids needing to update `tests/dashboard/test_code_page_arch_diagram.py` (which is not in scope).

## Preflight Results

| Check | Result |
|-------|--------|
| `make format` | ✅ All 672 files formatted |
| `make lint` | ✅ All checks passed (ruff + template checker) |
| `make typecheck` | ✅ No issues in 240 source files |

## Test Results

### Unit tests (pass ✅)
```
tests/dashboard/test_i00081_code_page_arch_diagram.py::test_render_arch_diagram_markdown_format   PASSED
tests/dashboard/test_i00081_code_page_arch_diagram.py::test_render_arch_diagram_bare_dsl        PASSED
```
These prove `_render_arch_diagram` correctly produces HTML with ≥3 `<pre data-lang="mermaid">` blocks, strips ELK front-matter, and strips the H1 for the Markdown path.

### Route integration tests (2 fail, reason: S03 template not updated)
```
tests/dashboard/test_i00081_code_page_arch_diagram.py::test_markdown_format_doc_renders_diagrams_not_syntax_error  FAILED
tests/dashboard/test_i00081_code_page_arch_diagram.py::test_api_code_architecture_endpoint_handles_markdown_doc      FAILED
tests/dashboard/test_i00081_code_page_arch_diagram.py::test_bare_dsl_format_still_renders_single_mermaid_div         PASSED
```
Root cause: `code_architecture_view.html` (line 47) only includes `code_architecture_diagram.html` when `{% if arch_diagram_dsl %}` — it has no guard for `arch_diagram_html`. S03 will fix this.

### Regression (existing tests pass ✅)
```
tests/dashboard/test_code_page_arch_diagram.py::TestI00055DoubleDiagram::test_code_page_renders_exactly_one_diagram          PASSED
tests/dashboard/test_code_page_arch_diagram.py::TestI00055DoubleDiagram::test_architecture_map_content_has_no_trailing_...     PASSED
tests/dashboard/test_code_page_arch_diagram.py::TestI00055DoubleDiagram::test_diagram_architecture_doc_renders_as_bottom_...   PASSED
tests/dashboard/test_code_page_arch_diagram.py::TestI00055DoubleDiagram::test_strip_helper_is_applied_to_arch_map_content      PASSED
```
No regression in existing arch-diagram rendering.

### Total: 7 passed, 2 expected-fail (will pass when S03 updates templates)

## Context Variables for S03

| Variable | Type | Purpose |
|----------|------|---------|
| `arch_diagram_html` | `str \| None` | Full rendered HTML for Markdown-doc form (≥3 `<pre data-lang="mermaid">` blocks with blockquote "Why" annotations) |
| `arch_diagram_dsl` | `str \| None` | Bare DSL string for legacy bare-DSL form |
| `arch_purpose` | `str \| None` | Purpose line from `<!-- purpose: -->` comment (bare-DSL only) |

## Notes

- The `_strip_elk_fm()` inner function strips ELK front-matter from each fenced block body (removes the leading `---\nconfig:\n  layout: elk\n---` block up to and including the closing `---`). This mirrors `_clean_diagram_dsl`'s existing behavior for the bare-DSL path.

- The `replacer` inner function returns the cleaned fence block as ` ```mermaid\n{cleaned_body}``` ` (no ELK front-matter), which `_preprocess_mermaid` then converts to `<pre data-lang="mermaid"><code>{body}</code></pre>`.

- The Markdown-doc path does NOT call `wrap_h2_sections_collapsible` (unlike `_render_architecture_html`) because the diagram doc has no H2 sections, only blockquotes + fences.

- The `code_architecture_view.html` template will need to be updated in S03 to render `arch_diagram_html` inside the diagram container (likely via the existing `code_architecture_diagram.html` fragment, adapted to handle the new HTML context var).