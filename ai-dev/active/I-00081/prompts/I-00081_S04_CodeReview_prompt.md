# I-00081_S04_CodeReview_prompt

**Work Item**: I-00081 — Code page "Architecture Diagram" widget shows "Syntax error in text — mermaid version 11.14.0"
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations. If S03 touched `orch/db/` or added a migration, CRITICAL (out of scope).

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00081 --json`.
- `ai-dev/active/I-00081/I-00081_Issue_Design.md` — design (read **Code Changes**, **Acceptance Criteria**).
- `ai-dev/active/I-00081/reports/I-00081_S01_backend-impl_report.md` — the context-var contract S03 had to match.
- `ai-dev/active/I-00081/reports/I-00081_S03_frontend-impl_report.md` — S03 report.
- S03's `files_changed` (expected: `dashboard/templates/fragments/code_architecture_diagram.html`, `dashboard/templates/fragments/code_architecture_view.html`).
- `dashboard/templates/components/libs/mermaid.html`, `dashboard/templates/project_code.html`, `dashboard/routers/code_ui.py` (S01's change) — to confirm the templates consume exactly the context vars the router produces.

## Output Files

- `ai-dev/active/I-00081/reports/I-00081_S04_CodeReview_report.md` — review report.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint          # MUST include scripts/check_templates.py — a template regression here is a CRITICAL finding
make format-check
```
Report only; fix nothing. Any NEW violation in S03's changed files → CRITICAL `"category":"conventions"` with file/line/exact message. **Pay special attention to `format`-filter usage in the templates** — any `str.format`-style `"{}m{}s"|format(...)` is a CRITICAL (raises `TypeError` at render time; see I-00075). (S03 likely added no `format` calls — but verify.)

## Review Checklist

1. **Markdown-doc form renders.** When `arch_diagram_html` (S01's var name — confirm from S01's report) is set, the fragment outputs it with `| safe` (NOT `| e` — it's server-rendered HTML; escaping it would show literal `<pre>` tags). The `<pre data-lang="mermaid">` blocks land inside `#code-arch-diagram` so `iwRenderMermaid(container)` (already called by the fragment's `<script>`) picks them up.
2. **Bare-DSL form still renders.** When `arch_diagram_dsl` is set (and `arch_diagram_html` is not), the fragment still emits `<div class="mermaid">{{ arch_diagram_dsl | e }}</div>` (escaped — raw DSL text), with the `{% if arch_purpose %}` line above it. If S01 folded everything into one var, confirm S03 matches that contract and that `tests/dashboard/test_code_page_arch_diagram.py` would still pass (it's not in scope — if it would now break, CRITICAL).
3. **Include guard widened.** `code_architecture_view.html`'s bottom guard is now `{% if arch_diagram_dsl or arch_diagram_html %}` (or `{% if arch_diagram_html %}` if folded) — so the Markdown-doc form actually gets included. If the guard still only checks `arch_diagram_dsl`, the Markdown-doc widget never renders → CRITICAL.
4. **No double rendering / no second mermaid init.** The fragment must not call `mermaid.initialize` or `mermaid.render` directly, must not include `components/libs/mermaid.html` a second time, and must not add a competing renderer. The single `<script>` calling `window.iwRenderMermaid(container)` is the only renderer. (`mermaid.html` is included once by `project_code.html`.) A second init or a stray `.mermaid` div around already-rendered HTML → HIGH (re-introduces the multi-error-box symptom).
5. **No out-of-scope edits.** Only the two fragment files changed (plus `ai-dev/active/I-00081/**`). `components/libs/mermaid.html`, `project_code.html`, `styles.css`, `*.js`, `code_ui.py`, `tests/*` unchanged. The `.prose-doc` style block (for `content_html`) unchanged. Anything else → CRITICAL.
6. **Fragment hygiene.** Fragments do not extend `base.html`. No inline `style=` where an existing class suffices. Accessibility: the rendered diagrams are SVGs produced client-side — nothing for the template to do, but confirm S03 didn't drop the `<h3>` heading or the `arch_purpose` paragraph.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_code_page_arch_diagram.py -v
make lint
```
Report results accurately. Do not run the full integration suite.

## Severity Levels & Result Contract

Standard severities. `verdict: pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE.

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00081",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [{"severity": "...", "category": "...", "file": "...", "line": 0, "description": "...", "suggestion": "..."}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
