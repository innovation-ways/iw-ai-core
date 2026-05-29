# I-00121_S05_CodeReview_Final_prompt

**Work Item**: I-00121 — Allure reports & summaries missing for make-based test categories
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

You MUST NOT run any command that changes Docker state. Allowed: testcontainer fixtures,
read-only `docker ps|inspect|logs`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migration in this item. Do not run `alembic upgrade|downgrade|stamp` against the live DB.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00121 --json`.
- `ai-dev/active/I-00121/I-00121_Issue_Design.md` — Design document.
- All step reports: `ai-dev/active/I-00121/reports/I-00121_S*_report.md`.
- All files changed across S01 + S03 (`orch/test_runner.py`, both test files).

## Output Files

- `ai-dev/active/I-00121/reports/I-00121_S05_CodeReview_Final_report.md` — Final review report.

## Context

Perform the **final cross-agent review** of all I-00121 work. Read the design doc first
(Acceptance Criteria + TDD Approach name both test files), then all reports, then review the
changed files holistically.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on all changed files. NEW violations → CRITICAL.

## Scope Diff — Directional, Not Symmetric (MANDATORY)

The intended production change is confined to `orch/test_runner.py`. Verify with directional
diffs:

```bash
git diff main...HEAD --name-only -- 'orch/**' 'dashboard/**' 'executor/**'
git log --name-only --pretty='%h %s' main..HEAD -- 'orch/**' 'dashboard/**' 'executor/**'
git status -s -- 'orch/**' 'dashboard/**' 'executor/**'
```

Only `orch/test_runner.py` should appear under `orch/**`; **no** `dashboard/**` changes (the
rendering fix shipped separately in eefcd837). Edits under `ai-dev/active|work/I-00121/**` are
not scope violations.

## Review Checklist (item-specific)

1. **Completeness vs design** — AC1 (make commands now emit Allure results via `PYTEST_ADDOPTS`),
   AC2 (`allure_report_dir` NULL when no report generated), AC3 (reproduction + persistence
   tests exist and pass). Both test files the design names must be present in some step's
   `files_changed` — missing = CRITICAL.
2. **Integration correctness** — `_build_run_command` is wired into `launch_test_run`; the
   pytest-direct path is unchanged (no duplicate `--alluredir`); `allure_report_dir` persistence
   is gated on `_generate_allure_report` success and nothing reads it earlier.
3. **No cross-cutting breakage** — quality runs (`run_type == "quality"`) and the dashboard
   Results tab (already gated on on-disk `index.html`) remain consistent with `allure_report_dir`
   now being NULL when no report exists.
4. **Test quality (holistic)** — semantic assertions (specific `--alluredir` value, exact
   NULL-vs-set persistence), testcontainer rules respected, deterministic.
5. **TDD RED evidence** — S01 (Backend) report carries plausible `tdd_red_evidence`.

## Test Verification (NON-NEGOTIABLE)

Run the **full test suite** (unit AND integration) and report results accurately. Integration
failures are CRITICAL. (This is the Final review — full-suite verification is expected here, in
contrast to the implementation steps.)

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00121",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {"severity": "...", "category": "...", "file": "...", "line": 0, "description": "...", "suggestion": "...", "cross_cutting": false}
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

`verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
