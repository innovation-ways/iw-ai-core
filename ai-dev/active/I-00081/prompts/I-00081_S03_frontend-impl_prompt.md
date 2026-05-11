# I-00081_S03_frontend-impl_prompt

**Work Item**: I-00081 — Code page "Architecture Diagram" widget shows "Syntax error in text — mermaid version 11.14.0"
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds no migrations and touches no database schema.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00081 --json`.
- `ai-dev/active/I-00081/I-00081_Issue_Design.md` — design document (read **Code Changes** and **Acceptance Criteria** in full).
- `ai-dev/active/I-00081/reports/I-00081_S01_backend-impl_report.md` — **read this first** for the exact new context-var name(s) S01 introduced (e.g. `arch_diagram_html`) and whether S01 kept `arch_diagram_dsl` as a separate var or folded everything into one. Match those names exactly.
- `dashboard/templates/fragments/code_architecture_diagram.html` — the file you change. Current body: an `{% if arch_purpose %}` line, an `<h3>Architecture Diagram</h3>`, a `.code-diagram-container` wrapping `<div class="mermaid">{{ arch_diagram_dsl | e }}</div>`, then a `<script>` that calls `window.iwRenderMermaid(container)` on `#code-arch-diagram`.
- `dashboard/templates/fragments/code_architecture_view.html` — the file you change. Near the bottom: `{% if arch_diagram_dsl %}{% include "fragments/code_architecture_diagram.html" %}{% endif %}`.
- `dashboard/templates/project_code.html` — includes `code_architecture_view.html` (line ~119). Reference only — you should not need to change it (it just passes through the context dict). Confirm it doesn't include `code_architecture_diagram.html` directly (it doesn't).
- `dashboard/templates/components/libs/mermaid.html` — the client-side renderer. `window.iwRenderMermaid(scope)` renders both `.mermaid:not([data-processed])` divs **and** `pre[data-lang="mermaid"]:not([data-processed])` blocks (it `mermaid.render()`s the `textContent` and swaps in the SVG, or shows a "Mermaid error: …" message in a `<pre>` on failure). Reference only — do NOT change it.
- `CLAUDE.md`, `dashboard/CLAUDE.md` — conventions. **In particular**: keep every Jinja2 `format`-filter call `%`-style (`"%dm%02ds"|format(m,s)`), never `str.format`-style — `make lint` → `scripts/check_templates.py` enforces this. Fragment templates MUST NOT extend `base.html` (these don't — keep it that way). If you add new Tailwind classes, `make css` may be needed — but prefer reusing existing classes; if `make css` reports "Nothing to be done" or the Tailwind CLI fails, append plain CSS to `dashboard/static/styles.css` (see I-00067) — though for this change you likely don't need any new CSS.

## Output Files

- `ai-dev/active/I-00081/reports/I-00081_S03_frontend-impl_report.md` — step report.
- Modified (expected): `dashboard/templates/fragments/code_architecture_diagram.html`, `dashboard/templates/fragments/code_architecture_view.html`.

## Context

S01 made `dashboard/routers/code_ui.py` format-aware: the `diagram-architecture` ProjectDoc may be the legacy **bare-DSL** form (rendered as before via `<div class="mermaid">{{ arch_diagram_dsl | e }}</div>` with an `arch_purpose` line) **or** the `iw-doc-generator` **Markdown-with-fences** form, which S01 pre-renders to HTML (containing one or more `<pre data-lang="mermaid">` blocks and the `> **Why this diagram?**` blockquotes) and passes as a new context var (read S01's report for the exact name — referred to below as `arch_diagram_html`). Your job: make the two fragments render whichever form is present.

## Requirements

### 1. `dashboard/templates/fragments/code_architecture_diagram.html`

Inside the existing `<div class="code-diagram-container">` (keep the surrounding `#code-arch-diagram` wrapper, the `{% if arch_purpose %}` paragraph, and the `<h3>Architecture Diagram</h3>` heading):

- If `arch_diagram_html` (S01's var) is set → render `{{ arch_diagram_html | safe }}` (it's server-rendered HTML — `| safe`, NOT `| e`). The `<pre data-lang="mermaid">` blocks inside it get picked up by `iwRenderMermaid`.
- Else if `arch_diagram_dsl` is set → keep the current `<div class="mermaid">{{ arch_diagram_dsl | e }}</div>` (escaped — it's raw DSL text).
- (If S01 folded everything into `arch_diagram_html` and removed `arch_diagram_dsl`, then just render `{{ arch_diagram_html | safe }}` unconditionally — match S01's actual contract.)
- Keep the trailing `<script>` that calls `window.iwRenderMermaid(container)` on `#code-arch-diagram` unchanged — it already handles both `.mermaid` and `pre[data-lang="mermaid"]`. Do not add a second renderer; do not call `mermaid.*` directly.
- Wrap the whole fragment in the appropriate guard so it produces nothing when neither var is set (the include guard in `code_architecture_view.html` already does this, but keep the fragment self-consistent — e.g. `{% if arch_diagram_html or arch_diagram_dsl %} … {% endif %}`, mirroring the existing `{% if arch_diagram_dsl %}` at the top).

### 2. `dashboard/templates/fragments/code_architecture_view.html`

Change the bottom include guard from `{% if arch_diagram_dsl %}` to `{% if arch_diagram_dsl or arch_diagram_html %}` (or to `{% if arch_diagram_html %}` if S01 folded everything into one var — match S01). Nothing else in this file changes.

### 3. Do NOT change

- `components/libs/mermaid.html`, `project_code.html`, `dashboard/static/*.js`, `dashboard/static/styles.css` (unless you genuinely need a new CSS rule — you probably don't), `dashboard/routers/*` (S01 owns the router), `tests/*` (S05 owns tests).
- The `.prose-doc` styling block in `code_architecture_view.html` (that's for `content_html`, the architecture-map render — leave it).

## Project Conventions

Read `dashboard/CLAUDE.md`. Match the existing fragment style. Keep `format`-filter calls `%`-style. Don't introduce inline `style="…"` if an existing class will do; the rendered `arch_diagram_html` already carries its own structure.

## TDD Requirement

Template-only changes can't really have a "RED" unit test of their own — the route/render regression tests are S05's job. Verify your change by rendering: either run the existing `tests/dashboard/test_code_page_arch_diagram.py` (must still pass — the bare-DSL path is unchanged), and/or do a quick manual render against a seeded Markdown-format doc if you can. Do NOT add a committed test file (that's S05).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`  2. `make typecheck`  3. `make lint` (this runs `scripts/check_templates.py` — your template change MUST pass it). Fix anything they report. Record each in `preflight`.

## Test Verification (NON-NEGOTIABLE — targeted only)

```bash
uv run pytest tests/dashboard/test_code_page_arch_diagram.py -v
make lint   # includes the Jinja2 template check
```
Do **NOT** run `make test-integration` / `make test-unit` (full suites — those are S11/S12 QV gates). Do not report `tests_passed: true` unless the targeted tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "I-00081",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/templates/fragments/code_architecture_diagram.html", "dashboard/templates/fragments/code_architecture_view.html"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Which S01 context-var name(s) you matched; whether you kept two branches or one; confirmation `make lint` (template check) passed."
}
```
