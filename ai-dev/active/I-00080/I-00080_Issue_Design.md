# I-00080: Docs-page document rendering — server-side Mermaid render is uncached and dark-mode-unaware (slow loads, white-on-white diagram labels, blank HTML/PDF tabs)

**Type**: Issue
**Severity**: High
**Created**: 2026-05-11
**Reported By**: User (sergio) — reproduced live on `iw-dev-01:9900`
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.) This item touches no Docker state.

## ⛔ Migrations: agents generate, daemon applies

This item adds **no migrations** and touches no database schema. The render cache is keyed to `ProjectDoc.version` using the **existing** `html_path` / `pdf_path` columns — same mechanism the PDF download already uses (`dashboard/routers/docs.py:225-229`), and `DocService.update_doc` already NULLs both columns when content changes (`orch/doc_service.py:212-213`).

## Description

Opening any document on the Docs page that contains a Mermaid diagram (`diagram-architecture`, per-module diagram docs, architecture docs, and anything `iw-doc-generator` produces with embedded diagrams) is slow and visually broken: the diagram is re-rendered server-side via headless Chromium **on every page load** (measured: ~33 s to open `/project/iw-ai-core/docs/diagram-architecture`; the HTML tab sat a blank white iframe for ~38 s before content appeared), and the rendered diagram labels compute to `color: rgb(255,255,255)` — **white text on the white diagram box → invisible in dark mode**. The PDF tab returns a bare HTTP 503 (blank iframe, no message) when the Chromium binary isn't available. Separately, `doc_type=diagram` docs that still hold raw Mermaid DSL (straight from the code-mapping pipeline, with no ` ```mermaid ` fence) render as a garbled `<hr>` / `<h2>` / paragraph mess.

## Project Context

Read the project's `CLAUDE.md` (and `dashboard/CLAUDE.md`, `orch/CLAUDE.md`) for architecture, conventions, and hard rules — in particular: routers are thin (logic lives in `orch/`); plain CSS goes directly into `dashboard/static/styles.css` when Tailwind can't recompile; `make lint` runs `scripts/check_templates.py`; never run `docker compose` against the orch DB; never run alembic against the live DB.

## Steps to Reproduce

1. On the dashboard, switch to **dark mode** (theme toggle in the footer).
2. Go to a project's **Docs** page (`/project/{id}/docs`).
3. Click **View** on the "Architecture Diagram" doc (`diagram-architecture`) — or any doc whose content contains a ` ```mermaid ` block.
4. Observe the page takes ~30 s to load.
5. On the **Markdown** tab, look at the diagram labels.
6. Click the **HTML** tab — observe a blank white iframe for ~30+ s.
7. Click the **PDF** tab — observe a blank iframe (or 503) if the PDF renderer's Chromium binary isn't found.

**Expected**: The doc page loads promptly; the diagram is readable in both light and dark mode; the HTML and PDF tabs show content (or a clear "unavailable" message) without a multi-second blank period; a diagram doc that holds raw DSL renders as a diagram, not as garbled text.

**Actual**: ~33 s page load (every time — no caching); diagram labels render white-on-white in dark mode; HTML/PDF tabs are blank for 30+ s on first view; PDF tab returns a bare 503 when Chromium is missing; raw-DSL diagram docs render as `<hr>`/`<h2>`/paragraphs of DSL.

## Browser Evidence

Captured pre-fix, in dark mode, against the live dashboard:

- `ai-dev/active/I-00080/evidences/pre/I-00080-darkmode-diagram-white-on-white.png` — Markdown tab of `diagram-architecture` in dark mode; the diagram is a white box on the dark page; edge labels ("SQL queries", "iw step-done / approve") and the "Platform (iw-ai-core repo)" group label are white/near-white on the white diagram background.
- `ai-dev/active/I-00080/evidences/pre/I-00080-html-tab.png` — HTML tab after ~38 s; same diagram, same label-contrast problem.
- `ai-dev/active/I-00080/evidences/pre/I-00080-snapshot.yml` — accessibility snapshot.
- Measured via `playwright-cli`: opening `/project/iw-ai-core/docs/diagram-architecture` took **33 069 ms**; the first `<foreignObject> <div>` label in the rendered SVG has computed style `color: rgb(255, 255, 255)`.

## Browser Verification Script (pre-fix reproduction)

```bash
playwright-cli kill-all
playwright-cli open "http://localhost:9900/project/iw-ai-core/docs"
playwright-cli eval "() => { document.documentElement.classList.add('dark'); localStorage.setItem('theme','dark'); }"
# time the load:
playwright-cli open "http://localhost:9900/project/iw-ai-core/docs/diagram-architecture"   # ~33 s
playwright-cli eval "() => document.querySelector('.mermaid-diagram svg foreignObject div, .prose-doc svg foreignObject div') && getComputedStyle(document.querySelector('.mermaid-diagram svg foreignObject div, .prose-doc svg foreignObject div')).color"  # → "rgb(255, 255, 255)"
playwright-cli screenshot
```

## Root Cause Analysis

`dashboard/utils/markdown.py`:
- `render_markdown_with_callouts(text, render_mermaid=True)` (`markdown.py:422`) — when the rendered HTML contains `language-mermaid`, calls `_render_mermaid_blocks` (`markdown.py:371`).
- `_render_mermaid_blocks` → `_render_mermaid_to_svg` (`markdown.py:268`) → `_render_mermaid_mmdc` (`markdown.py:291`) shells out to `npx @mermaid-js/mermaid-cli -i … -o … -b white --puppeteerConfigFile …` (30 s timeout), which launches a headless Chromium each call. On failure it falls back to `_render_mermaid_kroki` (`markdown.py:339`) — a `curl` to `https://kroki.io/mermaid/svg/…` (15–20 s). On total failure it keeps the raw `<pre><code>` block.
- **No caching whatsoever** — every call re-runs mmdc (and possibly the kroki `curl`).
- `mmdc` is invoked with no `-t <theme>` and no `-c <config>`; the only background hint is `-b white`. Mermaid's default `htmlLabels: true` puts node/edge label text in `<foreignObject>` `<div>` elements; the inline SVG, injected into the dashboard page, does not enforce a label colour, so the labels inherit the page's `color` and render white in dark mode (computed `rgb(255,255,255)` confirmed). The diagram box itself stays white (`-b white`) regardless of theme.

`dashboard/routers/docs.py` — every Docs-page render surface goes through the above:
- `docs_detail` (`docs.py:64-88`) — the page itself calls `render_markdown_with_callouts(doc.content)` **synchronously** at line 77, blocking the whole request for ~30 s on first view.
- `docs_html_view` (`docs.py:91-133`) — when `doc.html_path` is unset (true for code-mapping diagram docs and most `iw-doc-generator` docs, which write DB content, not branded HTML files on disk), falls back to inline render → another mmdc call; it never writes `html_path`, so it re-renders every time.
- `docs_pdf_view` (`docs.py:136-174`) — when `doc.pdf_path` is unset, generates on the fly via `render_markdown_with_callouts` + `render_pdf_chromium`; it never writes `pdf_path` (only the download route at `docs.py:225-229` does), so it re-renders every time; if `render_pdf_chromium` returns `None` it raises a bare `HTTPException(503)` → blank iframe with no user-facing explanation.
- `docs_pdf` (`docs.py:177-235`) — download; first call slow, then disk-cached on `pdf_path`.
- `docs_export_bundle` / `docs_export_single` (`docs.py:935-1003`) and the `iw docs-export` CLI (`orch/cli/doc_commands.py:420`) — same `render_markdown_with_callouts` path.

Raw-DSL diagram docs: `orch/rag/mapgen.py:185-222` stores `diagram-architecture` (and per-module diagram docs) as `<!-- purpose: … -->\n<bare Mermaid DSL>` — **not** wrapped in a ` ```mermaid ` fence. `docs_detail` runs that through the markdown converter, which turns the YAML frontmatter / DSL lines into `<hr>` (thematic break), a setext `<h2>` (the `---` after `config:` lines), and paragraphs. The Docs page has no notion of "this is a diagram doc — render it as a diagram", unlike the Code page (`dashboard/routers/code_ui.py` + `dashboard/templates/fragments/code_architecture_diagram.html`, which wraps the DSL in `<div class="mermaid">…</div>` and calls the theme-aware `window.iwRenderMermaid`).

**Why the I-00055 fix didn't cover this**: I-00055 ("Architecture Diagram renders twice on Code page; inline copy unreadable in dark mode") fixed the **Code page**, which renders Mermaid client-side via `dashboard/templates/components/libs/mermaid.html` (`mermaid.initialize({ theme: isDark ? 'dark' : 'base', … })`). The Docs detail page uses a completely different server-side `mmdc → inline SVG` path that I-00055 never touched. I-00074 ("PDF export missing diagram labels — WeasyPrint does not support SVG foreignObject") is the same foreignObject family but only addressed PDF export.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/utils/markdown.py` (`_render_mermaid_mmdc`, `_render_mermaid_to_svg`, `_render_mermaid_blocks`, `render_markdown_with_callouts`) | Server-side Mermaid render: no caching → slow every call; no deterministic theme/label colour → white-on-white in dark mode |
| `dashboard/routers/docs.py` (`docs_detail`, `docs_html_view`, `docs_pdf_view`, `docs_pdf`, `docs_export_*`) | Every Docs render surface re-renders on every request; `docs_pdf_view` raises a bare 503; `doc_type=diagram` raw-DSL docs are sent through markdown unchanged |
| `dashboard/templates/docs_detail.html` | Markdown tab embeds the server-rendered SVG; no client-side theme-aware fallback; no raw-DSL diagram handling |
| `dashboard/templates/research_detail.html` | Uses plain `render_markdown` — a research doc with a ` ```mermaid ` block shows raw DSL in a `<pre>`, never renders the diagram |
| `orch/cli/doc_commands.py` (`docs-export`) | Same `render_markdown_with_callouts` path → slow on export |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | `dashboard/utils/markdown.py`: render mmdc SVGs with a deterministic light theme + enforced dark label colours so labels are readable on any page background; keep the kroki fallback; keep the raw-`<pre>` fallback. (No in-process cache — caching is keyed to `ProjectDoc.version` in the router layer, S05.) | — |
| S02 | CodeReview | Review S01 output | — |
| S03 | frontend-impl | `dashboard/templates/docs_detail.html`: render Mermaid client-side on the interactive **Markdown** tab via `components/libs/mermaid.html` (theme-aware, instant — no server round-trip); detect `doc_type == 'diagram'` content that holds raw DSL and render it as a diagram, not garbled markdown. `dashboard/templates/research_detail.html`: same minimal client-side Mermaid treatment for parity. | — |
| S04 | CodeReview | Review S03 output | — |
| S05 | api-impl | `dashboard/routers/docs.py`: pass `render_mermaid=False` for the interactive markdown panel in `docs_detail` (the template renders diagrams client-side now); after `docs_html_view` renders the inline fallback, write it to `docs/.generated/{project}/{doc_id}-v{version}.html` and `update_doc(html_path=…)`, and serve from `html_path` when present; after `docs_pdf_view` generates a PDF, write it to `docs/.generated/{project}/{doc_id}-v{version}.pdf` and `update_doc(pdf_path=…)` (mirror `docs_pdf` at `docs.py:225-229`); when `render_pdf_chromium` returns `None`, return a small styled HTML "PDF unavailable" page with HTTP 200 instead of raising 503; when a `doc_type=diagram` doc's content has no ` ```mermaid ` fence, wrap it in one before rendering so it goes through the proper diagram path. | — |
| S06 | CodeReview | Review S05 output | — |
| S07 | tests-impl | Reproduction + regression tests (see Test to Reproduce / TDD Approach) | — |
| S08 | CodeReview | Review S07 output | — |
| S09 | CodeReview_Final | Global review of all work | — |
| S10..S14 | QV Gates | lint, format, typecheck, unit-tests, integration-tests | — |
| S15 | QV Browser | Browser verification — diagram doc loads fast, labels readable in dark mode, HTML/PDF tabs render or show a clear message | — |
| S16 | self-assess | Self-assessment via the iw-item-analyze skill | — |

Agent slugs: `backend-impl`, `frontend-impl`, `api-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None — the cache reuses the existing `project_docs.html_path` / `project_docs.pdf_path` columns, keyed to `ProjectDoc.version` (filename embeds `v{version}`; `DocService.update_doc` already NULLs both columns when content changes).
- **Migration notes**: None.

### Code Changes

- **Files to modify**: `dashboard/utils/markdown.py`, `dashboard/templates/docs_detail.html`, `dashboard/templates/research_detail.html`, `dashboard/routers/docs.py`; plus new test files `tests/dashboard/test_i00080_docs_diagram_render.py` (route/template tests, S07) and `tests/unit/test_markdown_mermaid_legibility.py` (markdown-util legibility test, added by S01 or S07).
- **Nature of change**: deterministic Mermaid theme + enforced label colour (markdown util); client-side theme-aware diagram render + raw-DSL diagram handling (templates); version-keyed disk cache for the HTML/PDF render surfaces + graceful PDF-unavailable response + `render_mermaid=False` for the interactive panel (router).

## File Manifest

All files for this work item live under `ai-dev/active/I-00080/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00080_Issue_Design.md` | Design | This document |
| `I-00080_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/I-00080_S01_backend-impl_prompt.md` | Prompt | S01 — Mermaid render theme/label-colour fix in `markdown.py` |
| `prompts/I-00080_S02_CodeReview_prompt.md` | Prompt | S02 — review of S01 |
| `prompts/I-00080_S03_frontend-impl_prompt.md` | Prompt | S03 — client-side diagram render + raw-DSL handling in `docs_detail.html` / `research_detail.html` |
| `prompts/I-00080_S04_CodeReview_prompt.md` | Prompt | S04 — review of S03 |
| `prompts/I-00080_S05_api-impl_prompt.md` | Prompt | S05 — version-keyed cache + graceful PDF fallback + `render_mermaid=False` in `docs.py` |
| `prompts/I-00080_S06_CodeReview_prompt.md` | Prompt | S06 — review of S05 |
| `prompts/I-00080_S07_tests-impl_prompt.md` | Prompt | S07 — reproduction + regression tests |
| `prompts/I-00080_S08_CodeReview_prompt.md` | Prompt | S08 — review of S07 |
| `prompts/I-00080_S09_CodeReview_Final_prompt.md` | Prompt | S09 — global review |
| `prompts/I-00080_S15_BrowserVerification_prompt.md` | Prompt | S15 — browser verification |
| `prompts/I-00080_S16_SelfAssess_prompt.md` | Prompt | S16 — self-assessment |

Reports are created during execution in `ai-dev/active/I-00080/reports/`.

## Test to Reproduce

**Test-file location**: these tests drive FastAPI routes / Jinja2 templates via the dashboard `client` fixture, so they MUST live under `tests/dashboard/` (the `client` fixture is registered only in `tests/dashboard/conftest.py`). Suggested file: `tests/dashboard/test_i00080_docs_diagram_render.py`.

```python
def test_i00080_diagram_doc_render_does_not_block_on_mmdc(client, ...):
    """A diagram doc whose content has a ```mermaid block must NOT cause the
    /docs/{doc_id} page to invoke the server-side mmdc renderer — the markdown
    panel is rendered client-side. FAILS before the fix (page calls
    render_markdown_with_callouts with render_mermaid=True), PASSES after."""
    # Arrange: seed a ProjectDoc with content containing a ```mermaid block.
    # Act: GET /project/{pid}/docs/{doc_id} with render_mermaid patched to raise
    #      if called (or assert the route passes render_mermaid=False).
    # Assert: response 200; the markdown panel contains the mermaid source in a
    #         client-renderable form (a `pre[data-lang="mermaid"]` or `div.mermaid`),
    #         NOT an <svg> produced by mmdc; the page includes the mermaid libs partial.

def test_i00080_rendered_svg_label_colour_is_dark(...):
    """When render_markdown_with_callouts DOES render a diagram to SVG (HTML/PDF
    paths), the output enforces a dark label colour so labels are never white.
    Assert the rendered HTML/SVG contains the enforced colour (e.g. a wrapper
    style or themeVariables) — assert the SPECIFIC expected colour token, not
    just 'there is a style attribute'."""

def test_i00080_html_view_caches_to_html_path(client, ...):
    """After GET /docs/{doc_id}/html-view on a doc with no html_path, the doc's
    html_path is set and points at an existing file under docs/.generated; a
    second GET serves the cached file (mmdc not re-invoked)."""

def test_i00080_pdf_view_unavailable_returns_200_not_503(client, ...):
    """When render_pdf_chromium returns None, GET /docs/{doc_id}/pdf-view returns
    HTTP 200 with an HTML 'PDF unavailable' body — not a bare 503."""

def test_i00080_raw_dsl_diagram_doc_renders_as_diagram(client, ...):
    """A doc_type=diagram doc whose content is bare Mermaid DSL (no ```mermaid
    fence — the orch/rag/mapgen.py shape) renders on /docs/{doc_id} as a
    client-renderable diagram block, NOT as <hr>/<h2>/paragraphs of DSL."""
```

## Acceptance Criteria

### AC1: Diagram docs render readably and fast

```
Given a project doc whose content contains a Mermaid diagram (fenced ```mermaid block or raw DSL in a doc_type=diagram doc)
When a user opens /project/{id}/docs/{doc_id} in dark mode
Then the page loads without a multi-second server-side render block
  And the diagram renders with the dashboard's dark theme, with all node and edge labels legible (no white-on-white)
```

### AC2: HTML and PDF tabs are fast and never blank-with-no-message

```
Given a diagram-bearing doc with no html_path / pdf_path on disk
When a user opens the HTML tab, then re-opens it
Then the first render is cached to html_path keyed by the doc's version, and the second open serves the cached file
  And when the PDF renderer's Chromium binary is unavailable, the PDF tab shows a clear "PDF unavailable" message (HTTP 200), not a blank iframe / bare 503
```

### AC3: Raw-DSL diagram docs are not garbled

```
Given a doc_type=diagram doc whose stored content is bare Mermaid DSL (no ```mermaid fence)
When a user opens it on the Docs page
Then it renders as a diagram, not as a sequence of horizontal rules, headings, and paragraphs of DSL text
```

### AC4: Bug is fixed (reproduction)

```
Given the fix is applied
When the browser verification script from this design runs against the diagram-architecture doc in dark mode
Then the page load is prompt, the diagram labels are dark/legible, and the HTML and PDF tabs render content (or a clear message)
```

### AC5: Regression tests exist

```
Given the fix is applied
When the test suite runs
Then the I-00080 reproduction and regression tests in tests/dashboard/test_i00080_docs_diagram_render.py pass
```

## Regression Prevention

- The interactive Docs markdown tab now uses the same theme-aware client-side Mermaid renderer as the Code page (`components/libs/mermaid.html`) — one render path, one place dark-mode behaviour is defined; future themes propagate automatically.
- The server-side `mmdc` render (still used for the standalone HTML/PDF surfaces) is given an explicit, deterministic theme + label colour, so the output is correct regardless of where the SVG is later embedded.
- HTML/PDF renders are cached on `ProjectDoc.html_path` / `pdf_path` keyed by version (filename embeds `v{version}`; `update_doc` NULLs them on content change) — repeat views never re-shell-out.
- `docs_pdf_view` always returns a renderable response — no bare 503.
- Regression tests assert the specific observable contract (client-renderable diagram block present, no mmdc `<svg>` on the markdown tab, enforced dark label colour token in the SVG path, `html_path` populated after first HTML view, 200 + message when Chromium is missing, raw-DSL diagram doc rendered as a diagram).

## Dependencies

- **Depends on**: None
- **Blocks**: None
- **Related (not blocking)**: I-00055 (Code-page inline diagram dark-mode fix — reference pattern), I-00074 (PDF foreignObject labels), I-00077 (doc-generation job failures — adjacent area, separate cause)

## Impacted Paths

- `dashboard/utils/markdown.py`
- `dashboard/routers/docs.py`
- `dashboard/templates/docs_detail.html`
- `dashboard/templates/research_detail.html`
- `tests/dashboard/test_i00080_docs_diagram_render.py`
- `tests/unit/test_markdown_mermaid_legibility.py`

## TDD Approach

- Reproducing test: `test_i00080_diagram_doc_render_does_not_block_on_mmdc` — fails before the fix (the `/docs/{doc_id}` page calls `render_markdown_with_callouts(..., render_mermaid=True)` and the markdown panel contains an mmdc-produced `<svg>`), passes after (markdown panel contains a client-renderable mermaid block and the libs partial; the route passes `render_mermaid=False`).
- Unit tests: `dashboard/utils/markdown.py` — `render_markdown_with_callouts` on content with a ` ```mermaid ` block, with mmdc available, produces an SVG whose label colour is the enforced dark token (assert the specific token); `render_mermaid=False` leaves the `language-mermaid` `<pre>` block intact for client-side rendering.
- Integration / dashboard tests: `docs_html_view` populates `html_path` and serves the cached file on the second call; `docs_pdf_view` returns 200 + an HTML "PDF unavailable" body when `render_pdf_chromium` returns `None`; a `doc_type=diagram` doc with bare-DSL content renders as a diagram block on `/docs/{doc_id}`.

**Assertion scoping**: when asserting a CSS class is present in rendered HTML, use the attribute-scoped form (`'class="mermaid"' in html` or a `class\s*=\s*"[^"]*mermaid[^"]*"` regex), not the bare-substring form (`"mermaid" in html` would false-positive on the libs `<script>`). Assert **specific** colour tokens / class names / status codes, not just "a style attribute exists" or "the response is non-empty".

## Notes

- Scope spans three implementation agents (Backend util + Frontend templates + API router) because the bug genuinely lives in all three layers and the user explicitly asked for every document surface to be covered, not just `diagram-architecture`. It is still a minimal fix — no refactor of the doc system, no new DB columns, no change to the doc-generation skills.
- The first load of the **HTML** tab on an uncached doc is still a one-time ~30 s `mmdc` render (it must produce a self-contained HTML file); after that it is disk-cached. This is acceptable for an explicit "view the rendered HTML" action and is called out so a reviewer doesn't treat it as an unfixed regression.
- Edge case the implementer should handle in S05: if the `docs_html_view` fallback render falls through to the raw `<pre>` block because `mmdc` is unavailable at request time (the rendered HTML still contains `language-mermaid`), do **not** write the `html_path` cache for that doc — otherwise the degraded (diagram-less) HTML is served permanently until the doc's content changes. Cache only a render that actually produced the SVG (or, equivalently, only cache when `mmdc` succeeded). The PDF view has the analogous consideration, but there the "PDF unavailable" branch already returns without writing `pdf_path`, so a transient Chromium absence doesn't poison the cache.
- The `iw docs-export` CLI and the `/api/docs/export` ZIP routes benefit from the S01 theme/label fix; they are not separately cached (export is a deliberate, infrequent action).
- Unrelated: the live `iw-dev-01` dashboard currently shows an "Orch DB schema is behind head — run `make db-migrate`" banner (visible in the pre-fix screenshots). That is not part of this incident; flagged for the operator.
