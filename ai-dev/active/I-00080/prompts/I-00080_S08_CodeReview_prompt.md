# I-00080_S08_CodeReview_prompt

**Work Item**: I-00080 — Docs-page document rendering: server-side Mermaid render is uncached and dark-mode-unaware
**Step Being Reviewed**: S07 (tests-impl)
**Review Step**: S08

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00080 --json`.
- `ai-dev/active/I-00080/I-00080_Issue_Design.md` — design (read **Test to Reproduce**, **Acceptance Criteria**, **TDD Approach** in full; write down every test file the design names by path and check it exists in S07's `files_changed` — a missing named test file is CRITICAL).
- `ai-dev/active/I-00080/reports/I-00080_S07_tests-impl_report.md` — S07 report.
- `ai-dev/active/I-00080/reports/I-00080_S01_...md`, `..._S03_...md`, `..._S05_...md` — to confirm the tests assert against the *actual* tokens/paths/wording the implementation used, not invented ones.
- All files in S07's `files_changed` (expected: `tests/dashboard/test_i00080_docs_diagram_render.py`, possibly `tests/unit/test_markdown_mermaid_legibility.py`).
- `tests/CLAUDE.md`, `tests/dashboard/conftest.py` — test conventions and the `client` fixture.

## Output Files

- `ai-dev/active/I-00080/reports/I-00080_S08_CodeReview_report.md` — review report.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on S07's `files_changed`, report only:
```bash
make lint
make format-check
```
Any NEW violation → CRITICAL (`"category":"conventions"`).

## Review Checklist (testing focus)

1. **Reproduction coverage** — there is a test that would FAIL against pre-fix code: specifically `test_i00080_docs_detail_markdown_panel_renders_diagram_client_side` (pre-fix the route called `render_markdown_with_callouts(..., render_mermaid=True)` and embedded an mmdc `<svg>`) and `test_i00080_raw_dsl_diagram_doc_renders_as_diagram` (pre-fix → garbled markdown). Confirm these exist and their assertions actually distinguish fixed from broken.
2. **Semantic correctness, not shape** — every assertion checks a specific value: scoped class assertions (`'class="mermaid"'` / a `class="..."` regex, not bare `"mermaid" in html`); the specific enforced dark colour token from S01's report (not "a `style=` exists"); `status_code == 200` AND a body-content check for the "PDF unavailable" path (not just `!= 503`); `html_path` set to an existing file whose path contains `v{version}`; the second HTML/PDF fetch served from cache. Flag any shape-only assertion as MEDIUM_FIXABLE (HIGH if it's the reproduction test).
3. **Tokens match reality** — the colour token, cache-dir path shape (`docs/.generated/{project}/{doc_id}-v{version}.{html,pdf}`), helper name, and "PDF unavailable" wording asserted in the tests match what S01/S05's reports say. If a test asserts an invented value, MEDIUM_FIXABLE (the test will pass by luck or fail spuriously).
4. **Test file location** — route/template-driven tests are under `tests/dashboard/` (not `tests/unit/` / `tests/integration/`); any pure-`markdown.py` test is under `tests/unit/`. Wrong location → CRITICAL (`fixture 'client' not found` at runtime, I-00067).
5. **Isolation / determinism** — uses testcontainer DB (never live 5433); seeds its own `ProjectDoc`s; monkeypatches `render_pdf_chromium` / `render_markdown_with_callouts` rather than depending on a real Chromium / mmdc; the mmdc-availability skip is only on the *legibility* unit test, NOT on the caching test (caching must be verified regardless). `FTS_FUNCTION_SQL`/`FTS_TRIGGER_SQL` applied if `create_all()` is used directly; no `importlib.reload(orch.config)`.
6. **No weakened assertions** — S07 must not have softened any assertion to make a test pass over an incomplete implementation; if a test is xfail/skip without a strong reason, HIGH.
7. **Conventions** — test names describe what they verify; fixtures reused, not reinvented; matches `tests/CLAUDE.md`.

## Test Verification (NON-NEGOTIABLE)

Run the new test file(s) yourself:
```bash
uv run pytest tests/dashboard/test_i00080_docs_diagram_render.py -v
```
Report the actual result. If a test fails, that's a finding (HIGH/CRITICAL depending on which). Do not run the full integration suite.

## Severity Levels & Result Contract

Standard severities. `verdict: pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE.

```json
{
  "step": "S08",
  "agent": "CodeReview",
  "work_item": "I-00080",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [{"severity": "...", "category": "testing|...", "file": "...", "line": 0, "description": "...", "suggestion": "..."}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (Y skipped)",
  "notes": ""
}
```
