# I-00050_S03_Tests_prompt

**Work Item**: I-00050 — Fix cycle prompt carries stale failure report instead of most recent run
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Testcontainers (via pytest fixtures) are the ONLY allowed Docker usage. Never run `docker compose` or `docker` commands directly. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00050/I-00050_Issue_Design.md` — bug description, acceptance criteria, "Test to Reproduce" section
- `ai-dev/active/I-00050/reports/I-00050_S01_Backend_report.md` — what was changed and where
- `orch/daemon/fix_cycle.py` — fixed `_get_browser_findings` function
- `tests/unit/test_fix_cycle.py` — existing unit tests for fix_cycle (add to this file)
- `tests/integration/test_fix_cycle.py` — existing integration tests (add to this file)
- `tests/CLAUDE.md` — test conventions and testcontainer pattern

## Output Files

- `ai-dev/active/I-00050/reports/I-00050_S03_Tests_report.md` — step report

## Context

Write tests that verify the bug fix for `_get_browser_findings`: when a browser-verification step has `report_file` set from run 1 (agent-reported failure), but run 2 failed with a daemon-detected error (`StepRun.report_file = None`, non-empty `error_message`), the function must prepend the latest run's error as the leading context.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "error" in findings` (shape only — doesn't prove the right error is first)
- GOOD: `assert findings.startswith("## ⚠️ Most Recent Failure")` (semantic — proves the prepend leads)
- GOOD: `assert findings.index("browser env setup failed") < findings.index("V1 FAIL")` (proves ordering)
- GOOD: `assert "e2e-dashboard-1 exited (1)" in findings` (proves specific new error is present)

## Requirements

### 1. Unit test — reproduction test (add to `tests/unit/test_fix_cycle.py`)

Write `test_i00050_get_browser_findings_uses_latest_run_error` using mocks (no DB):

- Mock the `db.execute(...)` call to return a `StepRun` with `run_number=2`, `report_file=None`, `error_message="browser env setup failed: e2e-dashboard-1 exited (1)"`, `status=RunStatus.failed`
- Provide a `WorkflowStep` with `report_content="## V1 FAIL\n..."`, `report_file=None` (so the disk path isn't read)
- Call `_get_browser_findings(mock_db, step, "/tmp/worktree")`
- Assert:
  - `"browser env setup failed"` is in the result
  - `"e2e-dashboard-1 exited (1)"` is in the result
  - The result starts with `"## ⚠️ Most Recent Failure (run 2)"` (or contains it before the V table)
  - `"V1 FAIL"` is still present (original report preserved)
  - `findings.index("browser env setup failed") < findings.index("V1 FAIL")`

### 2. Unit test — no-op when latest run has report_file (add to `tests/unit/test_fix_cycle.py`)

Write `test_i00050_get_browser_findings_unchanged_when_latest_run_has_report`:

- Mock the latest failed StepRun to have `report_file="reports/step_report.md"` (agent-reported)
- Provide a `WorkflowStep` with `report_content="## V1 FAIL original\n..."`
- Assert the result equals the original report content (no prepend, no change)
- This ensures AC3: existing behaviour is preserved when no newer daemon-detected failure exists

### 3. Integration test — full DB scenario (add to `tests/integration/test_fix_cycle.py`)

Write `test_i00050_get_browser_findings_integration` using the testcontainer fixture:

- Create a `Project`, `WorkItem`, and `WorkflowStep` (type `browser_verification`) in the DB
- Insert `StepRun` row 1: `run_number=1`, `status=RunStatus.failed`, `report_file="reports/bv_report.md"`, `error_message="ENV_DATA_MISSING: no callouts"`
  - Set `step.report_file = "reports/bv_report.md"` and `step.report_content = "| V1 | FAIL |\n..."`
- Insert `StepRun` row 2: `run_number=2`, `status=RunStatus.failed`, `report_file=None`, `error_message="browser env setup failed: e2e-dashboard-1 exited (1)"`
- Call `_get_browser_findings(db_session, step, "/tmp/fake_worktree")`
- Assert:
  - `"browser env setup failed"` in result
  - `"e2e-dashboard-1 exited (1)"` in result
  - `"V1"` and `"FAIL"` still present (V table preserved)
  - `result.index("browser env setup failed") < result.index("V1")`

### 4. Read test conventions carefully

Before writing, read `tests/CLAUDE.md` and `tests/conftest.py` for:
- The `pg_engine` and `db_session` fixture patterns
- How to create `Project`, `WorkItem`, `WorkflowStep`, `StepRun` rows in integration tests
- The FTS DDL requirement after `Base.metadata.create_all()`

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting completion, run in order:

1. `make format` — must run cleanly (auto-fixes drift, re-stage if it changes files)
2. `make typecheck` — zero errors on files you touched
3. `make lint` — zero errors (pay attention to ARG001 unused arguments, F811 redefinition)

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` and `make allure-integration` after writing tests. All tests must pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00050",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_fix_cycle.py",
    "tests/integration/test_fix_cycle.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```

Then call:
```bash
uv run iw step-done I-00050 --step S03 \
  --report ai-dev/active/I-00050/reports/I-00050_S03_Tests_report.md
```
