# F-00067 S05 Code Review — Frontend (S02)

## What was reviewed

S02 (Frontend — templates) implementation: callout CSS, JS parser, TOC generation, typographic hierarchy, purpose paragraph extraction, diagram fragments.

## Files reviewed

| File | Finding |
|------|---------|
| `dashboard/utils/markdown.py` | `render_markdown_with_callouts()` + `_convert_callout_blockquotes()` — server-side blockquote→callout conversion. ✓ |
| `dashboard/routers/docs.py` | `docs_detail()` and `docs_html_view()` use `render_markdown_with_callouts()` (line 78, 113). ✓ |
| `dashboard/templates/docs_detail.html` | CSS: callout colors match canonical palette, `callout-header` has `text-transform:uppercase; letter-spacing:0.05em`. H1/H2/H3 differentiated by weight AND color. `max-width:72ch` on paragraphs. TOC CSS + `@media (max-width:1279px)` hidden. `iwBuildToc()` and `iwProcessCallouts()` as progressive enhancement (JS-only). ✓ |
| `dashboard/routers/code_ui.py` | `code_page()` and `code_architecture()` extract `<!-- purpose: ... -->` via `re.search()` (lines 136, 266). ✓ |
| `dashboard/routers/code.py` | `get_module_diagram()` extracts `<!-- purpose: ... -->` (line 270). ✓ |
| `dashboard/templates/fragments/code_architecture_diagram.html` | `arch_purpose` slot conditionally rendered: `{% if arch_purpose %}...{% endif %}`. ✓ |
| `dashboard/templates/fragments/code_module_diagram.html` | `diagram_purpose` slot conditionally rendered: `{% if diagram_purpose %}...{% endif %}`. ✓ |
| `tests/dashboard/test_docs_callouts.py` | Tests for server-side callout rendering (callout-warning, callout-note, all 5 types, plain blockquote unchanged). ✓ |

## Review checklist — findings

1. **Callout CSS** — CSS values match canonical design spec:
   - `callout-note`: `#3B82F6` / `#EFF6FF` / `#1D4ED8` ✓
   - `callout-tip`: `#10B981` / `#ECFDF5` / `#065F46` ✓
   - `callout-warning`: `#F59E0B` / `#FFFBEB` / `#92400E` ✓
   - `callout-danger`: `#EF4444` / `#FEF2F2` / `#991B1B` ✓
   - `callout-important`: `#8B5CF6` / `#F5F3FF` / `#4C1D95` ✓
   - `callout-header`: `text-transform:uppercase; letter-spacing:0.05em` ✓

2. **Callout implementation — server-side primary path** ✓
   - `render_markdown_with_callouts()` in `dashboard/utils/markdown.py` does the conversion
   - `docs_detail()` and `docs_html_view()` call it (not `render_markdown()`)
   - Multi-line blockquote bodies handled via second `re.sub()` replacement ✓
   - Unknown types fall back via `TYPE_MAP.get(type_key, ("note", type_key))` — no crash ✓
   - Parser is case-insensitive via `re.IGNORECASE` flag ✓
   - No XSS risk: DOM node children moved, not raw string concat ✓
   - `iwProcessCallouts()` JS is progressive enhancement only, not primary path ✓

3. **Typographic hierarchy** ✓
   - H1: `font-weight:700; border-bottom:2px solid; padding-bottom:0.4em` ✓
   - H2: `font-weight:600; border-bottom:1px solid; padding-bottom:0.25em` ✓
   - H3: `font-weight:600; color:var(--muted-foreground)` ✓
   - Paragraphs: `max-width:72ch` ✓

4. **TOC** ✓
   - `iwBuildToc()` strips non-alphanumeric chars, replaces spaces with `-` before assigning `h.id`
   - Only rendered when `headings.length >= 3`
   - Hidden on `max-width:1279px` via `@media` ✓

5. **Purpose paragraph extraction** ✓
   - `code_ui.py:136` and `code.py:270`: `re.search(r'<!-- purpose: (.*?) -->', content)`
   - `code_ui.py:138`: `arch_purpose = m.group(1).strip()` (None-safe since `m` checked before `.group()`)
   - Templates use `{% if arch_purpose %}` / `{% if diagram_purpose %}` — no template error on missing marker ✓

6. **Regression check** ✓
   - `view-html` and `view-pdf` tabs: `switchDocTab()` + lazy iframes preserved ✓
   - Plain blockquote styling preserved in `.prose-doc blockquote` rule ✓
   - Mermaid rendering: `iwRenderMermaid()` in fragment `<script>` blocks ✓

## Test results

```
make test-unit → 2004 passed, 2 skipped, 48 warnings (39.68s)
```

No failures. The 2 skipped and warnings are pre-existing (unrelated to this step).

## Verdict

**pass**

All checklist items resolved. No mandatory fixes.