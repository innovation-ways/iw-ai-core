# F-00067_S02_Frontend_prompt

**Work Item**: F-00067 — Documentation Visual Design Overhaul
**Step**: S02
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ No live DB migrations

No schema changes required for this step.

---

## Input Files

- `ai-dev/active/F-00067/F-00067_Feature_Design.md` — Design doc (§Callout Rendering Spec, §Semantic Color Palette)
- `dashboard/templates/docs_detail.html` — Main doc rendering template
- `dashboard/templates/fragments/code_architecture_diagram.html` — Arch diagram fragment
- `dashboard/templates/fragments/code_module_diagram.html` — Module diagram fragment
- `dashboard/routers/docs.py` (or wherever `content_html` is computed) — Markdown→HTML pipeline

## Output Files

- `dashboard/templates/docs_detail.html` — Modified
- `dashboard/templates/fragments/code_architecture_diagram.html` — Modified
- `dashboard/templates/fragments/code_module_diagram.html` — Modified
- `dashboard/static/docs/callouts.css` (new) OR inline styles in template — Callout CSS
- `ai-dev/active/F-00067/reports/F-00067_S02_Frontend_report.md` — Step report

---

## Context

The docs detail page currently renders markdown as basic HTML with minimal styling — headings differ only in font-size, blockquotes are just italic with a left border, and there is no TOC or callout support. This step adds:
1. Richer typographic hierarchy (H1/H2/H3 differentiated by weight + color, not just size)
2. GitHub-style callout blocks (`[!NOTE]`, `[!WARNING]`, `[!DANGER]`, `[!TIP]`, `[!IMPORTANT]`)
3. Auto-generated in-page Table of Contents for documents with ≥3 H2/H3 headings
4. "Why" purpose paragraph slot in architecture and module diagram fragments

---

## Requirements

### 1. Enhanced typographic hierarchy in `.prose-doc`

Locate the `<style>` block inside `#view-markdown` in `dashboard/templates/docs_detail.html` (around line 192). Replace the heading styles with:

```css
.prose-doc h1 {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--foreground);
  border-bottom: 2px solid var(--border);
  padding-bottom: 0.4em;
  margin-top: 0;
  margin-bottom: 0.6em;
}
.prose-doc h2 {
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--foreground);
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.25em;
  margin-top: 1.8em;
  margin-bottom: 0.5em;
}
.prose-doc h3 {
  font-size: 1rem;
  font-weight: 600;
  color: var(--muted-foreground);
  margin-top: 1.4em;
  margin-bottom: 0.4em;
}
.prose-doc h4 {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--muted-foreground);
  margin-top: 1.2em;
  margin-bottom: 0.3em;
}
```

Also update body copy for better readability:
```css
.prose-doc p { line-height: 1.8; max-width: 72ch; }
```

### 2. Callout / admonition CSS

Add a new CSS block (either inline in the template's `<style>` tag or as `dashboard/static/docs/callouts.css` loaded in `base.html` for doc pages) with these classes:

```css
.callout {
  border-left: 4px solid;
  border-radius: 0 var(--radius) var(--radius) 0;
  padding: 0.75em 1em;
  margin: 1.25em 0;
  font-size: 0.9rem;
}
.callout-header {
  display: flex;
  align-items: center;
  gap: 0.4em;
  font-weight: 600;
  margin-bottom: 0.4em;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.callout-note    { border-color: #3B82F6; background: #EFF6FF; }
.callout-note    .callout-header { color: #1D4ED8; }
.callout-tip     { border-color: #10B981; background: #ECFDF5; }
.callout-tip     .callout-header { color: #065F46; }
.callout-warning { border-color: #F59E0B; background: #FFFBEB; }
.callout-warning .callout-header { color: #92400E; }
.callout-danger  { border-color: #EF4444; background: #FEF2F2; }
.callout-danger  .callout-header { color: #991B1B; }
.callout-important { border-color: #8B5CF6; background: #F5F3FF; }
.callout-important .callout-header { color: #4C1D95; }
```

### 3. Callout JS parser

In `docs_detail.html`, after the `content_html` is injected into `.prose-doc`, add a JavaScript block that post-processes the rendered HTML to convert GitHub-style callout blockquotes into `.callout` divs.

The parser must:
- Select all `blockquote` elements inside `.prose-doc`
- For each blockquote, check if its first `<p>` starts with `[!NOTE]`, `[!TIP]`, `[!WARNING]`, `[!DANGER]`, or `[!IMPORTANT]` (case-insensitive)
- If matched: replace the `blockquote` with a `<div class="callout callout-{type}">` containing a `callout-header` div with icon + label, and a `callout-body` div with the remaining content
- If not matched: leave the blockquote untouched

Icon mapping:
- `note` → `ℹ️`
- `tip` → `💡`
- `warning` → `⚠️`
- `danger` → `🚨`
- `important` → `📌`

The JS function should be named `iwProcessCallouts(container)` and called once after the DOM is ready with `document.querySelector('.prose-doc')` as the argument.

### 4. Auto-generated in-page Table of Contents

Add a TOC generator that runs after content is loaded:

- Collect all `h2` and `h3` elements inside `.prose-doc`
- If there are fewer than 3, skip TOC entirely
- For each heading, ensure it has an `id` attribute (generate one from the text if missing: lowercase, spaces → hyphens, strip non-alphanumeric)
- Render a TOC as a `<nav class="doc-toc">` containing a nested `<ul>` — H2 as top-level items, H3 as indented sub-items
- Insert the TOC immediately before `.prose-doc` (or in a designated `#doc-toc-container` slot if you add one)
- TOC CSS: floating right sidebar on wide viewports (≥ 1280px), hidden below that

TOC CSS classes:
```css
.doc-toc { position: sticky; top: 1rem; font-size: 0.8rem; max-width: 220px; float: right; margin-left: 1.5rem; margin-bottom: 1rem; border-left: 2px solid var(--border); padding-left: 0.75rem; }
.doc-toc ul { list-style: none; padding: 0; margin: 0; }
.doc-toc > ul > li { margin-bottom: 0.35em; }
.doc-toc > ul > li > ul { padding-left: 0.75em; margin-top: 0.25em; }
.doc-toc a { color: var(--muted-foreground); text-decoration: none; }
.doc-toc a:hover { color: var(--foreground); }
@media (max-width: 1279px) { .doc-toc { display: none; } }
```

The JS function should be named `iwBuildToc(container)`.

### 5. "Why" purpose paragraph in diagram fragments

**`dashboard/templates/fragments/code_architecture_diagram.html`:**

The architecture diagram's `arch_diagram_dsl` content (loaded from `ProjectDoc.content`) may now start with a `<!-- purpose: ... -->` comment (added by S01). Extract and render it:

Add a Jinja2 macro or inline Jinja logic:
```jinja2
{% set purpose_match = arch_diagram_dsl | regex_search('<!-- purpose: (.*?) -->') if arch_diagram_dsl else None %}
{% if purpose_match %}
<p class="text-sm text-muted-foreground italic mb-3">{{ purpose_match }}</p>
{% endif %}
```

Note: Jinja2 does not have a built-in `regex_search` filter. Instead, extract the purpose in the Python router (`dashboard/routers/code_ui.py`) before passing to the template:
- After loading `arch_diagram_doc.content`, use `re.search(r'<!-- purpose: (.*?) -->', content)` to extract `arch_purpose`
- Pass `arch_purpose` as a separate template variable
- In the template, render `{% if arch_purpose %}<p ...>{{ arch_purpose }}</p>{% endif %}` above the diagram

**`dashboard/templates/fragments/code_module_diagram.html`:**

Same approach — extract purpose from `diagram_dsl` in `dashboard/routers/code.py` (in `get_module_diagram()`) and pass as `diagram_purpose` template variable. Render above the diagram.

---

## Project Conventions

- Dashboard is FastAPI + Jinja2 + htmx. No React, no build step.
- All JS is vanilla, loaded from `dashboard/static/`. No npm.
- CSS lives in templates (inline `<style>` blocks) or `dashboard/static/` (loaded via `base.html`).
- Follow existing htmx fragment patterns — fragments are returned by HTMX endpoints.
- Read `dashboard/CLAUDE.md` for dashboard-specific conventions.

## TDD Requirement

The frontend layer is Jinja2 + vanilla JS — no unit test framework for JS. However, callout detection **MUST be implemented server-side** (not exclusively in JavaScript) so that the FastAPI test client can verify it. Implement callout post-processing in Python:

- In `dashboard/utils/markdown.py`, add a `render_markdown_with_callouts(text)` function that calls `render_markdown()` then passes the result through a Python HTML post-processor (`re.sub` or `html.parser`) to convert `<blockquote><p>[!TYPE]...</p></blockquote>` patterns into `<div class="callout callout-{type}">` elements.
- Use `render_markdown_with_callouts()` instead of `render_markdown()` wherever docs are rendered in `dashboard/routers/docs.py`.
- The `iwProcessCallouts(container)` JS function (§3 above) becomes optional progressive enhancement for any callouts that may be added dynamically after page load — it should NOT be the primary rendering path.

**Why server-side**: the FastAPI test client does not execute JavaScript. A test that asserts `.callout-warning` in the response HTML will only pass if conversion happens before the response is sent.

1. **RED**: Add a `tests/dashboard/test_docs_callouts.py` that renders a doc with known callout content via the FastAPI test client and asserts the response HTML contains the string `callout-warning` and `callout-note` (as class attributes on rendered div elements).
2. **GREEN**: Implement `render_markdown_with_callouts()` to pass the test.
3. Verify the template renders without Jinja2 errors by running `make test-unit` (dashboard tests are in `tests/dashboard/`).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit`

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "frontend-impl",
  "work_item": "F-00067",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/docs_detail.html",
    "dashboard/templates/fragments/code_architecture_diagram.html",
    "dashboard/templates/fragments/code_module_diagram.html",
    "dashboard/routers/code_ui.py",
    "dashboard/routers/code.py"
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
