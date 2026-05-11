# I-00080_S03_frontend-impl_prompt

**Work Item**: I-00080 — Docs-page document rendering: server-side Mermaid render is uncached and dark-mode-unaware (slow loads, white-on-white diagram labels, blank HTML/PDF tabs)
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds no migrations and touches no database schema. This is a Jinja2-template-only change — no Python, no routes, no DB. (S05 makes the matching route change in `dashboard/routers/docs.py`.)

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00080 --json`.
- `ai-dev/active/I-00080/I-00080_Issue_Design.md` — design document (read first; especially **Root Cause Analysis** and **AC1 / AC3**).
- `ai-dev/active/I-00080/evidences/pre/` — pre-fix screenshots (`I-00080-darkmode-diagram-white-on-white.png`, `I-00080-html-tab.png`).
- `ai-dev/active/I-00080/reports/I-00080_S01_backend-impl_report.md` — S01 report (the server-side render fix; not strictly needed here but read it for context).
- `dashboard/templates/docs_detail.html` — the file you change. The Markdown panel renders `{{ content_html | safe }}` inside `<div class="prose-doc …">` at ~line 219-220; there's already an inline `<style>` for `.prose-doc` and a `<script>` block at the bottom (`switchDocTab`, `iwProcessCallouts`, `iwBuildToc`, the `DOMContentLoaded` handler).
- `dashboard/templates/research_detail.html` — second file you change. Renders `{{ content_html | safe }}` inside `<div class="prose-doc …">` at ~line 130, with its own `<style>` and a `<script>` at ~line 161.
- `dashboard/templates/components/libs/mermaid.html` — the theme-aware client-side Mermaid renderer (`mermaid.initialize({ theme: isDark ? 'dark' : 'base', securityLevel:'loose' })`; exposes `window.iwRenderMermaid(root)` which upgrades `.mermaid:not([data-processed])` divs and `pre[data-lang="mermaid"]:not([data-processed])` blocks). Include this partial; do **not** modify it (it's shared by the Code page, item detail, chat).
- `dashboard/templates/project_code.html` (line 10: `{% include "components/libs/mermaid.html" %}`) and `dashboard/templates/fragments/code_architecture_diagram.html` (renders `<div class="mermaid">{{ arch_diagram_dsl | e }}</div>` then calls `window.iwRenderMermaid(container)`) — the reference pattern from I-00055. Reference only.
- `dashboard/routers/docs.py` — read `docs_detail` (~line 64-88) and `render_markdown_with_callouts` so you understand what `content_html` will contain after S05 passes `render_mermaid=False`. Do **not** edit it (that's S05).
- `CLAUDE.md`, `dashboard/CLAUDE.md` — conventions (Jinja2 `format`-filter rule; plain CSS into `styles.css` when Tailwind can't recompile; `make lint` runs `scripts/check_templates.py`; `make css` after adding new Tailwind classes — avoid adding new Tailwind classes if you can use plain CSS).

## Output Files

- `ai-dev/active/I-00080/reports/I-00080_S03_frontend-impl_report.md` — step report.
- Modified (expected): `dashboard/templates/docs_detail.html`, `dashboard/templates/research_detail.html`.

## Context

The Docs detail page (`docs_detail.html`, Markdown tab) currently embeds a **server-rendered** Mermaid SVG that the route produced via headless Chromium — slow (every load) and white-on-white in dark mode (its labels inherit the page `color`). After S05, the route will pass `render_mermaid=False` to `render_markdown_with_callouts` for the interactive panel, so `content_html` will contain `<pre><code class="language-mermaid">…dsl…</code></pre>` blocks **unrendered**. Your job: render those blocks **client-side** with the existing theme-aware renderer, exactly like the Code page does — instant, and correctly themed in dark mode.

Two further things on the Docs page:
1. `doc_type=diagram` docs may store their content as **bare Mermaid DSL** (no ` ```mermaid ` fence — the `orch/rag/mapgen.py` shape, e.g. `<!-- purpose: … -->\n---\nconfig:\n  layout: elk\n---\ngraph TD\n  …`). Run through the markdown converter that becomes garbled `<hr>`/`<h2>`/paragraphs. The Docs page must recognise this and render it as a diagram. The route (S05) will normalise the common case by wrapping bare-DSL `doc_type=diagram` content in a ` ```mermaid ` fence before rendering — so by the time it reaches the template it'll be a `language-mermaid` `<pre>` block like everything else. Your client-side upgrade therefore handles it for free, **as long as your shim also handles the `<!-- purpose: … -->` HTML comment line** that prefixes the DSL (strip it, or leave it — Mermaid ignores `%%` comments but not `<!-- -->`; safest: when extracting the DSL text from a `language-mermaid` block, strip a leading `<!-- … -->` line and any leading/trailing blank lines before handing it to Mermaid). Coordinate with S05's report — if S05 strips the comment server-side, you don't need to.
2. `research_detail.html` uses plain `render_markdown` (no Mermaid handling at all), so a research doc with a ` ```mermaid ` block currently shows raw DSL in a `<pre>`. Give it the same client-side treatment for parity.

## Requirements

### 1. Client-side Mermaid on the Docs Markdown tab — `dashboard/templates/docs_detail.html`

- `{% include "components/libs/mermaid.html" %}` near the top of the `{% block content %}` (or wherever the other library includes live — match `project_code.html:10`).
- The markdown converter emits `<pre><code class="language-mermaid">…</code></pre>` for fenced mermaid blocks. `window.iwRenderMermaid` looks for `.mermaid` divs and `pre[data-lang="mermaid"]` — **not** `pre > code.language-mermaid`. So add a small shim (in the existing `<script>` block, run on `DOMContentLoaded` *before* the `iwRenderMermaid` call): for each `pre > code.language-mermaid` inside `.prose-doc`, take its `textContent`, strip a leading `<!-- … -->` line + surrounding blank lines, create `<div class="mermaid">…dsl…</div>`, and `replaceChild` the `<pre>` with it; then call `window.iwRenderMermaid(proseDocEl)`. (Put this alongside the existing `iwProcessCallouts(proseDoc)` / `iwBuildToc(proseDoc)` calls; order: convert-to-`.mermaid`-divs first, then `iwRenderMermaid`.)
  - Be defensive: if `window.iwRenderMermaid` is undefined (partial failed to load) leave the `<pre>` blocks as-is (readable raw DSL) — don't throw.
  - Use the same `htmlClass.contains('dark')`-aware behaviour the partial already provides; you don't need to re-detect the theme.
- Do **not** change the HTML / PDF / IDE tabs or `switchDocTab` — those iframes are unchanged.
- Keep the `.prose-doc pre` styling but make sure a successfully-rendered diagram is visible: the rendered `<div class="mermaid">` will contain an `<svg>`; if the existing `.prose-doc` rules constrain it oddly, add a minimal rule (plain CSS in the page's `<style>` block, e.g. `.prose-doc .mermaid svg { max-width:100%; height:auto; }` and a light card background so a dark-themed diagram on a dark page still has a frame if needed). Don't add new Tailwind utility classes (no `make css` needed for plain CSS in a `<style>` block).

### 2. Client-side Mermaid on the Research detail page — `dashboard/templates/research_detail.html`

- Same treatment: `{% include "components/libs/mermaid.html" %}`, the same `pre > code.language-mermaid` → `<div class="mermaid">` shim in its `<script>` block, then `window.iwRenderMermaid`. Keep it minimal — research docs rarely have diagrams, but parity matters and the cost is one include + ~15 lines of JS.

### 3. Do not break callouts or the TOC

`iwProcessCallouts` and `iwBuildToc` already run on `.prose-doc`. Your mermaid-upgrade shim must not interfere — run it on the same `.prose-doc` element, before `iwBuildToc` (so a converted `<div class="mermaid">` isn't mistaken for a heading — it won't be, but order it first anyway) and it's fine before or after `iwProcessCallouts`.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. **Jinja2 `format`-filter rule**: any `|format(...)` call must be `%`-style (`"%dm%02ds"|format(m,s)`), never `str.format`-style — `make lint` → `scripts/check_templates.py` enforces it. Plain CSS goes directly into a `<style>` block or `dashboard/static/styles.css`; do not rely on a Tailwind recompile in worktrees. Match the existing JS style in these templates (vanilla, no framework).

## TDD Requirement

This is a template change; the regression tests live in S07 (`tests/dashboard/test_i00080_docs_diagram_render.py`). For your own verification, after the change, render the templates via the dashboard `client` fixture in a quick local check (or eyeball with `playwright-cli` against a running dashboard if available) and confirm: the Markdown tab of a diagram doc contains a `<div class="mermaid">` (or a `pre[data-lang="mermaid"]`) and the libs `<script src="…/mermaid.min.js">` — not an mmdc `<svg>` produced server-side.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting completion, run in order and fix what they report:
1. `make format`
2. `make typecheck`
3. `make lint` (runs `scripts/check_templates.py` + `node --check` on JS — your inline `<script>` must be valid JS)

Record each in the `preflight` object. STOP and raise a blocker if a tool is unavailable.

## Test Verification (NON-NEGOTIABLE)

Run the targeted dashboard tests that touch these templates if any exist (`uv run pytest tests/dashboard/ -k "docs_detail or research" -v`). Do **NOT** run `make test-integration` (full suite — that's a downstream QV gate). Run `make lint` on your touched files. Do not report `tests_passed: true` unless targeted tests pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "I-00080",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/templates/docs_detail.html", "dashboard/templates/research_detail.html"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Whether you strip the leading <!-- purpose --> comment in the shim or rely on S05 to do it server-side; any plain-CSS rules added; confirmation the libs partial is included on both pages."
}
```
