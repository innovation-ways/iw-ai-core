# I-00121_S04_CodeReview_Tests_prompt

**Work Item**: I-00121 — Allure reports & summaries missing for make-based test categories
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT run any command that changes Docker state. Allowed: testcontainer fixtures,
read-only `docker ps|inspect|logs`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migration in this item. Do not run `alembic upgrade|downgrade|stamp` against the live DB.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00121 --json`.
- `ai-dev/active/I-00121/I-00121_Issue_Design.md` — Design (Test to Reproduce + TDD Approach name both test files).
- `ai-dev/active/I-00121/reports/I-00121_S03_Tests_report.md` — S03 report.
- The test files in S03's `files_changed`.
- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md`.

## Output Files

- `ai-dev/active/I-00121/reports/I-00121_S04_CodeReview_report.md` — Review report.

## Context

Review the test coverage from S03. Read the design doc first and note both test files it names
by path: `tests/unit/test_test_runner_allure_env.py` and
`tests/integration/test_test_runner_report_persistence.py`. If either is missing from S03's
`files_changed`, that is a **CRITICAL** finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. NEW violations in changed files
are CRITICAL findings (`category: conventions`).

## Review Checklist (item-specific)

1. **Reproduction test targets the bug** — the `make` → `PYTEST_ADDOPTS` unit test would FAIL
   against pre-fix code (no `PYTEST_ADDOPTS` injected for make commands) and PASS after.
   Reason about this explicitly.
2. **Semantic correctness, not shape** — assertions check the **run-scoped `--alluredir` value**
   reaching pytest (not merely that `PYTEST_ADDOPTS` appears), and that the pytest-direct
   branch gets **no** duplicate `--alluredir`. The persistence test asserts the exact
   NULL-vs-set outcome of `run.allure_report_dir`, and asserts the specific parsed `summary`
   (not just "summary is truthy"). Flag any assertion that would still pass if the fix
   regressed.
3. **Coverage completeness** — both command shapes covered (make + pytest-direct), the
   passthrough/no-op case covered, append-safety covered if S01 implemented it, and BOTH
   persistence cases covered (report generated → dir set + summary; no results → dir NULL +
   `_generate_allure_report` not called).
4. **Testcontainer + isolation rules** — the integration test obeys `tests/CLAUDE.md`: psycopg
   URL replacement, FTS DDL after `create_all`, never the live DB (5433), no
   `importlib.reload(orch.config)`, no real subprocess / real `allure generate` (must be
   monkeypatched). Tests are deterministic and isolated.
5. **File placement** — pure-function tests under `tests/unit/`, DB-backed test under
   `tests/integration/` (per `tests/CLAUDE.md`).
6. **Scope** — only the two test files (+ any minimal fixture helper) changed. Directional diff
   (`git diff main...HEAD --name-only`). `ai-dev/active|work/I-00121/**` is not scope creep.

## Test Verification (NON-NEGOTIABLE)

Run the two new test files to confirm they pass:
`uv run pytest tests/unit/test_test_runner_allure_env.py tests/integration/test_test_runner_report_persistence.py -v`.
Do not run the full suite.

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00121",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {"severity": "...", "category": "testing", "file": "tests/...", "line": 0, "description": "...", "suggestion": "..."}
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
