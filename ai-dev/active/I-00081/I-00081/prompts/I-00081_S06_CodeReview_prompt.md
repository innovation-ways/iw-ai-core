# I-00081_S06_CodeReview_prompt

**Work Item**: I-00081 — Code page "Architecture Diagram" widget shows "Syntax error in text — mermaid version 11.14.0"
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations. If S05 added/touched anything under `orch/db/migrations/`, CRITICAL (out of scope).

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00081 --json`.
- `ai-dev/active/I-00081/I-00081_Issue_Design.md` — design (read **Test to Reproduce**, **Acceptance Criteria**, **TDD Approach**, **Regression Prevention** in full).
- `ai-dev/active/I-00081/reports/I-00081_S01_backend-impl_report.md`, `..._S03_frontend-impl_report.md`, `..._S05_tests-impl_report.md` — what was implemented and what S05 says it asserted.
- S05's `files_changed` (expected: `tests/dashboard/test_i00081_code_page_arch_diagram.py`).
- `tests/dashboard/test_code_page_arch_diagram.py` — the existing file S05 must NOT have modified (and which must still pass).
- `skills/iw-ai-core-testing/SKILL.md` — the testing skill `tests/CLAUDE.md` now mandates: assertion-strength rules ("would this fail if the production line were deleted?"), the test red-flag checklist, isolation rules. Judge S05's tests against it.
- `dashboard/routers/code_ui.py` (post-S01), `dashboard/templates/fragments/code_architecture_diagram.html` / `code_architecture_view.html` (post-S03) — to judge whether S05's assertions target the *actual* implementation.

## Output Files

- `ai-dev/active/I-00081/reports/I-00081_S06_CodeReview_report.md` — review report.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```
Report only. Any NEW violation in S05's new file → CRITICAL `"category":"conventions"` with file/line/exact message.

## Review Checklist

1. **Reproduction test is real.** `test_i00081_markdown_format_diagram_doc_renders_diagrams_not_raw_markdown` seeds the **actual** `iw-doc-generator` Markdown shape (multi-`#`/`>`/fence, with `---\nconfig:\n  layout: elk\n---` per block) and asserts properties that are FALSE against pre-fix code (≥2 `<pre data-lang="mermaid">` from the diagram doc; diagram bodies present; the literal fence string NOT inside a `class="mermaid"` element; `layout: elk` not in the rendered HTML). If the test would pass against pre-fix code, it's not a reproduction test → HIGH. (You can reason about pre-fix behaviour from S01's report; you don't need to run pre-fix code.)
2. **Semantic, not shape.** Assertions check **specific values** (`"flowchart TB" in html`, `"erDiagram" in html`, `html.count('<pre data-lang="mermaid">') >= 2`, `html.count('<div class="mermaid">') == 1` for the bare-DSL test, the purpose-line text) and the **absence** of bug markers — not just "a `<pre>`/`<div>` exists". A test that only checks `"mermaid" in html` (false-positives on `mermaid.min.js` / `language-mermaid`) or `resp.status_code == 200` → MEDIUM_FIXABLE.
3. **CSS-class assertion scoping (I-00067).** Any "class is present" assertion uses the attribute-scoped form (`'class="mermaid"' in html` or a `class\s*=\s*"[^"]*\bmermaid\b[^"]*"` regex), not the bare substring. A bare `"mermaid" in html` → MEDIUM_FIXABLE.
4. **Coverage of the design's AC.** AC1 (Markdown form renders, no raw-Markdown leak) — test 1 + test 4 (the htmx fragment route). AC2 (bare-DSL form unchanged, existing test file still green) — test 2 + S05 confirming `test_code_page_arch_diagram.py` is untouched and passing. AC3 — the file exists, is in S05's `files_changed`. Leading-H1-not-duplicated edge case — test 3. If any AC has no corresponding assertion → HIGH.
5. **Isolation & determinism.** Tests use the testcontainer `db_session` / `client` fixture pattern (never the live DB — `tests/CLAUDE.md`); seed data is created per-test and committed before the `GET`; no reliance on row IDs from other tests; the `architecture-map` doc seeded in tests is free of inline ```mermaid fences where that would make a `<pre data-lang="mermaid">` count ambiguous. No `importlib.reload(orch.config)`; `monkeypatch.delenv` if env is touched. The new file lives under `tests/dashboard/` (it uses the `client` fixture). Flaky/order-dependent → HIGH.
6. **No source edits, no scope creep.** S05 changed only the new test file (plus `ai-dev/active/I-00081/**`). It did NOT modify `tests/dashboard/test_code_page_arch_diagram.py`, `code_ui.py`, or the templates. Anything else → CRITICAL.

## Test Verification (NON-NEGOTIABLE)

Run S05's file and the existing one:
```bash
uv run pytest tests/dashboard/test_i00081_code_page_arch_diagram.py -v
uv run pytest tests/dashboard/test_code_page_arch_diagram.py -v
```
Report results accurately. Do not run the full integration suite (that's the S12 QV gate).

## Severity Levels & Result Contract

Standard severities. `verdict: pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE.

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00081",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [{"severity": "...", "category": "...", "file": "...", "line": 0, "description": "...", "suggestion": "..."}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (Y skipped)",
  "notes": ""
}
```
