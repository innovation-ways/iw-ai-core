# I-00080_S04_CodeReview_prompt

**Work Item**: I-00080 — Docs-page document rendering: server-side Mermaid render is uncached and dark-mode-unaware
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations. If S03 added an alembic file or touched the DB, CRITICAL (out of scope).

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00080 --json`.
- `ai-dev/active/I-00080/I-00080_Issue_Design.md` — design (read **Root Cause Analysis**, **AC1 / AC3**, **TDD Approach**).
- `ai-dev/active/I-00080/reports/I-00080_S03_frontend-impl_report.md` — S03 report.
- All files in S03's `files_changed` (expected: `dashboard/templates/docs_detail.html`, `dashboard/templates/research_detail.html`).
- `dashboard/templates/components/libs/mermaid.html` and `dashboard/templates/fragments/code_architecture_diagram.html` — the reference client-side pattern. Confirm `mermaid.html` was **not** modified.

## Output Files

- `ai-dev/active/I-00080/reports/I-00080_S04_CodeReview_report.md` — review report.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on S03's `files_changed`, report only:
```bash
make lint            # includes scripts/check_templates.py + node --check on JS
make format-check
```
Any NEW violation → CRITICAL finding (`"category":"conventions"`). Pay specific attention to: a `|format(...)` filter call that is NOT `%`-style (the I-00075 Jinja2 trap) — if S03 introduced one, CRITICAL. And `node --check` failing on the inline `<script>` (invalid JS) — CRITICAL.

## Review Checklist

1. **Does the Markdown tab now render diagrams client-side?** `{% include "components/libs/mermaid.html" %}` is present on `docs_detail.html` (and `research_detail.html`); a shim converts `pre > code.language-mermaid` blocks inside `.prose-doc` into `<div class="mermaid">…</div>` (stripping a leading `<!-- … -->` comment line) and then calls `window.iwRenderMermaid` on the `.prose-doc` element. The shim runs on `DOMContentLoaded`, before `iwBuildToc`. No mmdc `<svg>` is embedded by the page anymore (that comes from the route now being `render_mermaid=False` — verify S03's report notes this dependency on S05; if S05 hasn't run yet that's expected, not a finding).
2. **Defensive** — if `window.iwRenderMermaid` is undefined, the `<pre>` blocks are left intact (readable raw DSL) and nothing throws. Verify there's a guard.
3. **`mermaid.html` not modified** — it's shared (Code page, item detail, chat). If S03 changed it, MEDIUM_FIXABLE unless the change is provably safe for all consumers (then MEDIUM_SUGGESTION with a note).
4. **No collateral damage** — callouts (`iwProcessCallouts`) and TOC (`iwBuildToc`) still work; the HTML / PDF / IDE tab iframes and `switchDocTab` are unchanged; no new Tailwind utility classes added without `make css` (plain CSS in `<style>` is fine).
5. **Both pages covered** — `research_detail.html` got the same treatment (parity, per design Requirement 2).
6. **Conventions / quality / security** — vanilla JS matching the existing style; no inline event handlers that violate CSP-ish patterns the project uses elsewhere; no secrets; valid JS (`node --check` clean).

## Test Verification (NON-NEGOTIABLE)

Run targeted dashboard tests touching these templates (`uv run pytest tests/dashboard/ -k "docs_detail or research" -v` or the closest existing ones). Report results accurately. Do not run the full integration suite.

## Severity Levels & Result Contract

Standard severities. `verdict: pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE.

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00080",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [{"severity": "...", "category": "...", "file": "...", "line": 0, "description": "...", "suggestion": "..."}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
