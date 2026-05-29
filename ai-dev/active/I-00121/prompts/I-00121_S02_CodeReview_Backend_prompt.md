# I-00121_S02_CodeReview_Backend_prompt

**Work Item**: I-00121 — Allure reports & summaries missing for make-based test categories
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT run any command that changes Docker state. Allowed: testcontainer fixtures,
read-only `docker ps|inspect|logs`, `./ai-core.sh` / `make`. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migration. You MUST NOT run `alembic upgrade|downgrade|stamp` against the
live DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00121 --json` (authoritative step state).
- `ai-dev/active/I-00121/I-00121_Issue_Design.md` — Design document.
- `ai-dev/active/I-00121/reports/I-00121_S01_Backend_report.md` — S01 report.
- All files in S01's `files_changed` (notably `orch/test_runner.py`).

## Output Files

- `ai-dev/active/I-00121/reports/I-00121_S02_CodeReview_report.md` — Review report.

## Context

Review the Backend fix from S01. Read the design doc first (Acceptance Criteria + TDD
Approach + Notes), then the S01 report, then the changed files.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Any NEW violation in changed
files is a **CRITICAL** finding (`category: conventions`) quoting the exact code/message.

## Review Checklist (item-specific)

1. **PRIMARY fix correctness** — In `_build_run_command`, the `make` branch injects
   `PYTEST_ADDOPTS` containing `--alluredir=<run-scoped results_rel>`. Verify:
   - The run-scoped relative dir (not the static `allure-results`) reaches the `--alluredir`.
   - The injection is **append-safe** for a pre-existing `PYTEST_ADDOPTS` (an existing value
     is preserved, not clobbered), and an unset value expands to empty without breaking the
     shell command (runs under `shell=True`).
   - The value is correctly quoted (the space between `--alluredir=...` and any existing
     addopts must not split into separate shell tokens).
   - The **pytest-direct** branch does NOT also get `PYTEST_ADDOPTS` (would duplicate
     `--alluredir`). Confirm only the `make` branch is affected.
2. **SECONDARY fix correctness** — `run.allure_report_dir` is now assigned **only after**
   `_generate_allure_report` returns success (not unconditionally before the run). Verify the
   old unconditional assignment at the top of `launch_test_run` is gone, and that
   `run.summary` is still only set when stats parse. Confirm no code path reads
   `run.allure_report_dir` between launch and generation that would now break.
3. **Helper purity** — `_build_run_command` is a pure function (no DB/IO beyond `Path` math),
   module-level, and unit-testable. `launch_test_run` delegates to it with identical behaviour
   for the existing two branches.
4. **Quality runs** — confirm the S01 report states whether `dashboard/routers/quality.py`
   depends on `allure_report_dir` for quality runs, and that the conclusion is correct
   (quality runs never generated reports; NULL is acceptable).
5. **Scope** — only `orch/test_runner.py` (+ S01's RED unit test file) changed. Use a
   directional diff (`git diff main...HEAD --name-only`). No dashboard files touched. Edits
   under `ai-dev/active/I-00121/**` and `ai-dev/work/I-00121/**` are NOT scope creep.
6. **TDD RED evidence** — S01 is a Backend step: confirm `tdd_red_evidence` is present and
   plausible (an `AssertionError` from the missing `PYTEST_ADDOPTS`, not an import/collection
   error), and reason about whether the test would actually fail against pre-fix code.

## Test Verification (NON-NEGOTIABLE)

Run the targeted unit tests for the changed module
(`uv run pytest tests/unit -k test_runner -v`) to confirm no regression. Report results
accurately. (Full-suite runs are the QV gates' job.)

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW (standard meanings).

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00121",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {"severity": "...", "category": "...", "file": "orch/test_runner.py", "line": 0, "description": "...", "suggestion": "..."}
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
