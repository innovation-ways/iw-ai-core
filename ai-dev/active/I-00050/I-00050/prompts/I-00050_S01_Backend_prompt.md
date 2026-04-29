# I-00050_S01_Backend_prompt

**Work Item**: I-00050 — Fix cycle prompt carries stale failure report instead of most recent run
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00050/I-00050_Issue_Design.md` — full bug description and fix plan
- `orch/daemon/fix_cycle.py` — the file to modify (function `_get_browser_findings`, lines 589–623)
- `orch/db/models.py` — `StepRun` model (fields: `run_number`, `report_file`, `error_message`, `status`)

## Output Files

- `ai-dev/active/I-00050/reports/I-00050_S01_Backend_report.md` — step report

## Context

You are fixing a bug where `_get_browser_findings` in `orch/daemon/fix_cycle.py` always returns the failure report from the first `iw step-fail` call, making newer daemon-detected failures (container crashes, env setup failures) invisible to fix-cycle agents.

**Root cause**: `step.report_file` and `step.report_content` are step-level fields set once by `iw step-fail` on the first agent-reported failure and never updated. When subsequent runs fail due to daemon-detected errors (e.g., "browser env setup failed: dashboard container exited (1)"), those only write to `StepRun.error_message`. The function's "last resort" query of `StepRun.error_message` at line 607 is dead code whenever `step.report_file` is already set.

## Requirements

### 1. Fix `_get_browser_findings` to detect and surface newer failures

Modify `_get_browser_findings` (`orch/daemon/fix_cycle.py:589`) as follows:

After reading the report content from `step.report_file` / `step.report_content` (the existing logic), query for the **most recent failed `StepRun`** for this step. Check whether that run:
- Has `report_file = None` (daemon-detected failure, not agent-reported), AND
- Has a non-empty `error_message`

If both conditions are true, the latest run represents a **newer failure** that post-dates the original report. Prepend a `## ⚠️ Most Recent Failure (run N)` section to the returned content so the fix agent sees the current blocking issue first, with the original V table preserved below as secondary context.

**Exact behaviour to implement**:

```python
# After obtaining `content` from step.report_file / step.report_content:
from sqlalchemy import select
latest_failed = db.execute(
    select(StepRun)
    .where(
        StepRun.step_id == step.id,
        StepRun.status.in_([RunStatus.failed, RunStatus.timeout]),
    )
    .order_by(StepRun.run_number.desc())
    .limit(1)
).scalar_one_or_none()

if latest_failed and not latest_failed.report_file and latest_failed.error_message:
    content = (
        f"## ⚠️ Most Recent Failure (run {latest_failed.run_number})\n\n"
        f"{latest_failed.error_message}\n\n"
        "---\n\n"
        "## Original Browser Report (for V table context)\n\n"
        + content
    )
return _truncate(content, 8000)
```

Apply this injection at each of the three exit paths (after reading from `report_file`, after reading from `report_content`, and at the existing "last resort" path — though the last resort path already returns the latest error and needs no change).

### 2. Update the function docstring

Add a note to `_get_browser_findings`'s docstring explaining that:
- `step.report_file` / `step.report_content` reflect run 1's agent-reported failure
- Newer daemon-detected failures (no `report_file` on the `StepRun`) are prepended as the leading context
- The original report is always preserved for V table context

### 3. No other changes

Do NOT modify `_get_review_findings`, `_latest_failure_reason`, `attempt_fix_cycle`, or any other function. Scope is strictly `_get_browser_findings`.

## Project Conventions

Read the project's `CLAUDE.md` for:
- SQLAlchemy 2.0 style (`select()`, `.scalar_one_or_none()`, not `db.query()` — though existing code uses both; use `select()` for new queries to match newer style)
- No mocking in integration tests — use testcontainers
- Run `make format`, `make typecheck`, `make lint` before completing

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write a failing test that calls `_get_browser_findings` with a step that has `report_file` set from run 1, plus a newer `StepRun` (run 2) with `report_file=None` and a different `error_message`. Assert the result leads with the new error. This test MUST fail before your fix.
2. **GREEN**: Apply the fix. The test must pass.
3. **REFACTOR**: Ensure the no-op case (latest run has `report_file` set — original behaviour) still passes its test.

You may write the tests in `tests/unit/test_fix_cycle.py` (mocking the DB) as the RED phase, then implement the fix, then run `make test-unit` to verify GREEN.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting completion, run in order:

1. `make format` — auto-fixes formatting drift
2. `make typecheck` — zero errors on files you touched
3. `make lint` — zero errors

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` after implementation. Do NOT report `tests_passed: true` unless ALL unit tests pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00050",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/fix_cycle.py"
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
uv run iw step-done I-00050 --step S01 \
  --report ai-dev/active/I-00050/reports/I-00050_S01_Backend_report.md
```
