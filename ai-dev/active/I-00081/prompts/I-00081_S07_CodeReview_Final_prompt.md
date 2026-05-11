# I-00081_S07_CodeReview_Final_prompt

**Work Item**: I-00081 — Code page "Architecture Diagram" widget shows "Syntax error in text — mermaid version 11.14.0"
**Step**: S07 — Global cross-agent review
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations and no DB schema change. If any step added one, CRITICAL.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00081 --json`.
- `ai-dev/active/I-00081/I-00081_Issue_Design.md` — design (read in full: **Root Cause Analysis**, **Code Changes**, **Acceptance Criteria AC1–AC3**, **TDD Approach**, **Impacted Paths**, **Notes**).
- `ai-dev/active/I-00081/I-00081_Functional.md` — functional summary.
- All step reports: `ai-dev/active/I-00081/reports/I-00081_S0{1..6}_*_report.md`.
- All changed files across the item: `dashboard/routers/code_ui.py`, `dashboard/templates/fragments/code_architecture_diagram.html`, `dashboard/templates/fragments/code_architecture_view.html`, `tests/dashboard/test_i00081_code_page_arch_diagram.py`.
- `dashboard/templates/components/libs/mermaid.html`, `dashboard/templates/project_code.html` — to confirm nothing shared was changed and the include chain is intact.
- `tests/dashboard/test_code_page_arch_diagram.py` — must be unchanged and still passing.
- `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/rag/CLAUDE.md`, `tests/CLAUDE.md`.

## Output Files

- `ai-dev/active/I-00081/reports/I-00081_S07_CodeReview_Final_report.md` — global review report.

## What to verify (integration & completeness)

1. **Router ↔ template contract matches.** The context-var name(s) S01 introduced in `code_ui.py` (e.g. `arch_diagram_html`) are exactly the ones `code_architecture_diagram.html` consumes and the ones the `code_architecture_view.html` include-guard checks. If S01 produces `arch_diagram_html` but the fragment still only reads `arch_diagram_dsl` (or the guard still only checks `arch_diagram_dsl`), the Markdown-doc widget renders nothing → CRITICAL. Trace it for **both** entry points: `code_page` → `project_code.html` → `code_architecture_view.html` → `code_architecture_diagram.html`, **and** `code_architecture` (htmx route) → `code_architecture_view.html` → `code_architecture_diagram.html`.
2. **Both content shapes work end-to-end.**
   - Markdown-with-fences form: comments stripped; leading `# …` H1 dropped; per-block `---\nconfig:\n  layout: elk\n---` stripped; rendered via `_preprocess_mermaid` + `render_markdown` → `<pre data-lang="mermaid">` blocks → `iwRenderMermaid` (the single `<script>` in the fragment) renders them. No `class="mermaid"` element ends up containing the raw Markdown / literal fences. No `layout: elk` reaches the client.
   - Bare-DSL `mapgen` form: unchanged — `<div class="mermaid">` + the `<!-- purpose: -->` line; the existing `tests/dashboard/test_code_page_arch_diagram.py` still passes (run it). If S01 folded everything into one var and that test would now fail, that's a CRITICAL (scope must be amended by the operator, not silently — and `test_code_page_arch_diagram.py` is NOT in this item's `scope.allowed_paths`).
3. **No double rendering.** Exactly one Mermaid renderer runs: `components/libs/mermaid.html` is included once (by `project_code.html`); the fragment's `<script>` calls `window.iwRenderMermaid(container)` once; no fragment calls `mermaid.initialize`/`mermaid.render` directly; no stray `.mermaid` div wraps already-rendered HTML. (The pre-fix symptom included *three* "Syntax error" boxes — confirm the fix doesn't leave a path that double/triple-renders.)
4. **Acceptance criteria** — walk AC1–AC3 against the actual code + tests. AC1's "no Syntax error box / renders in the browser" is verified by S13 (browser), but sanity-check the change set could plausibly satisfy it (especially the ELK-front-matter strip — without it, S13 will still see errors). AC3: `tests/dashboard/test_i00081_code_page_arch_diagram.py` exists, is in S05's `files_changed`, and asserts semantic values (not shape) against the *actual* implementation markers.
5. **Scope discipline.** Only the files in **Impacted Paths** changed (plus `ai-dev/active/I-00081/**`): `code_ui.py`, the two fragments, the one new test file. No new DB column, no migration, no change to `mapgen.py` / the doc-generation skills, no edit to `components/libs/mermaid.html` (shared), no edit to `tests/dashboard/test_code_page_arch_diagram.py`, no edit to `dashboard/utils/markdown.py` or `_render_architecture_html`. Anything outside scope → CRITICAL (or HIGH + "operator must amend `scope.allowed_paths`" if it's a legitimate unavoidable fix).
6. **Lint / format / type clean across the whole change set.**
   ```bash
   make lint          # includes scripts/check_templates.py — a template regression is CRITICAL
   make format-check
   make typecheck
   ```
   New violations → CRITICAL. Any `str.format`-style Jinja `format` filter in the templates → CRITICAL (I-00075).
7. **Latent-path distrust.** The Code page route is a GET that now renders more HTML — no new DB writes, no new auth surface. Confirm `_render_arch_diagram` (or whatever S01 named it) doesn't accidentally call `DocService.update_doc` / bump `ProjectDoc.version` / write a version snapshot (it must only *read*). Confirm it doesn't import anything that pulls a DB engine at module-import time into a path a `tests/unit/` test would import (`tests/CLAUDE.md` gotcha) — it's in `code_ui.py` which already imports `SessionLocal` transitively, so a `tests/dashboard/` test is fine, but a `tests/unit/` import of it is not.

## Test Verification (NON-NEGOTIABLE)

Run the I-00081 test file, the existing arch-diagram test file, and a broad Code-page slice:
```bash
uv run pytest tests/dashboard/test_i00081_code_page_arch_diagram.py -v
uv run pytest tests/dashboard/test_code_page_arch_diagram.py -v
uv run pytest tests/dashboard/ -k "code" -v
```
Report results. Do not run the full integration suite (that's the S12 QV gate).

## Severity Levels & Result Contract

Standard severities. `verdict: pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE across all of S01–S06.

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00081",
  "verdict": "pass|fail",
  "findings": [{"severity": "...", "category": "...", "file": "...", "line": 0, "description": "...", "suggestion": "...", "step_origin": "S0X"}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (Y skipped)",
  "ac_check": {"AC1": "pass|fail|deferred-to-S13", "AC2": "pass|fail", "AC3": "pass|fail"},
  "notes": ""
}
```
