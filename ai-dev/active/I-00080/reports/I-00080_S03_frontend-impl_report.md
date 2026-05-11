# I-00080 S03 Frontend-impl Report

## What was done

Implemented client-side Mermaid rendering on the Docs and Research detail pages, replacing the slow server-side mmdc render with the existing theme-aware `window.iwRenderMermaid` client renderer.

### Changes to `dashboard/templates/docs_detail.html`

1. Added `{% include "components/libs/mermaid.html" %}` at the top of `{% block content %}` (line 7), matching the pattern in `project_code.html:10`. This loads the mermaid library and initialises it with the page's dark/light theme (`isDark ? 'dark' : 'base'`).

2. Added CSS rules inside the `<style>` block for the rendered diagram SVG (line 219-220):
   ```css
   .prose-doc .mermaid svg { max-width:100%; height:auto; }
   .prose-doc .mermaid-diagram svg { max-width:100%; height:auto; }
   ```
   This ensures diagrams scale responsively and the existing `.mermaid-diagram` wrapper div (from the server-side render path) also respects max-width.

3. Extended the `DOMContentLoaded` handler (lines 390-413) with a shim that runs **before** `iwProcessCallouts` and `iwBuildToc`:
   - Finds all `pre > code.language-mermaid` inside `.prose-doc`
   - For each: extracts `textContent`, strips a leading `<!-- purpose: ... -->` HTML comment and surrounding blank lines (the mapgen shape), creates a `<div class="mermaid">`, replaces the `<pre>` with it
   - Calls `window.iwRenderMermaid(proseDoc)` once all blocks are upgraded
   - Falls back silently if `window.iwRenderMermaid` is not yet defined (partial load failure)

### Changes to `dashboard/templates/research_detail.html`

1. Added `{% include "components/libs/mermaid.html" %}` at the top of `{% block content %}` (line 6).
2. Added the same shim inside a new `DOMContentLoaded` handler (lines 186-204):
   - Same `pre > code.language-mermaid` → `<div class="mermaid">` conversion
   - Same `<!-- purpose: ... -->` strip
   - Then `window.iwRenderMermaid(proseDoc)`

### Design decisions

- **Shim ordering**: Mermaid upgrade runs first, before `iwBuildToc`, so a converted `<div class="mermaid">` is never accidentally picked up as a heading by the TOC builder.
- **Defensive `window.iwRenderMermaid` check**: if mermaid.min.js fails to load, the raw `<pre>` blocks remain visible as readable DSL rather than throwing.
- **`<!-- purpose: ... -->` strip**: the shim strips a leading HTML comment (and any surrounding blank lines) from the DSL text before handing it to Mermaid, because Mermaid ignores `%%` comments but not `<!-- -->`. This handles the mapgen raw-DSL shape. If S05 strips this comment server-side the regex simply finds nothing to strip — no harm done.
- **No new Tailwind classes**: SVG sizing rules are plain CSS inside the existing `<style>` block; no `make css` required.
- **Parity**: research_detail.html gets identical treatment so any future research doc with a Mermaid diagram renders correctly.

## Files changed

- `dashboard/templates/docs_detail.html` — mermaid include, shim, SVG CSS rules
- `dashboard/templates/research_detail.html` — mermaid include, shim

## Preflight

| Check | Result |
|-------|--------|
| `make format` | ok — 670 files already formatted |
| `make typecheck` | ok — no issues in 240 source files |
| `make lint` | ok — all checks passed (includes `scripts/check_templates.py`) |

## Test results

Targeted dashboard tests (`tests/dashboard/` filtered by `docs_detail or research`):
```
tests/dashboard/test_docs_running_jobs.py::TestRunningJobsResearchExcluded::test_running_jobs_no_research_docs PASSED
tests/dashboard/test_empty_states.py::TestEmptyStateRendering::test_research_empty_state PASSED
tests/dashboard/test_help_router.py::TestHelpFragmentEndpoint::test_known_slug_returns_200_with_correct_headings[research] PASSED
tests/dashboard/test_help_router.py::TestHelpRouterSlugMappingCR00044::test_research_slug_maps_to_dashboard_design PASSED
tests/dashboard/test_help_router.py::TestHelpRouterNoHardcodedOldLinks::test_no_hardcoded_docs_or_orch_href[research] PASSED
```
5 passed, 0 failed. No I-00080-specific tests exist yet (those will be written in S07 by tests-impl).

## Notes

- The shim converts `pre > code.language-mermaid` (which the markdown converter emits for fenced mermaid blocks) into `div.mermaid` format that `window.iwRenderMermaid` already handles natively — no duplication of render logic.
- The `render_mermaid=False` flag that prevents the server-side mmdc call is applied by S05 in `dashboard/routers/docs.py`; this template change is independent and correct regardless of whether S05 has landed.
- The `<!-- purpose: ... -->` HTML comment strip uses a multiline regex (`/^<!--[\s\S]*?-->\s*/m`) that strips the comment and any trailing blank lines from the start of the DSL text. Blank lines at both ends are trimmed with `.trim()` before passing to Mermaid.
- The mermaid partial is included inside `{% block content %}` on both pages (not in `{% block head %}`), which is slightly unusual but consistent with how `project_code.html` structures it — the partial self-initialises on `DOMContentLoaded` so placement is not critical.
