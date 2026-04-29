# I-00050: Fix cycle prompt carries stale failure report instead of most recent run

**Type**: Issue
**Severity**: High
**Created**: 2026-04-29
**Reported By**: iw-item-analyze (post-execution analysis of F-00067, finding [1])
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No database schema changes required for this fix.

## Description

When a browser-verification step fails and a fix cycle is triggered, the daemon builds the fix-cycle prompt by calling `_get_browser_findings`. That function unconditionally reads `step.report_file` / `step.report_content` — step-level fields that are set once by `iw step-fail` on the first agent-reported failure and never updated again. If subsequent runs fail for a different reason (e.g., "browser env setup failed: dashboard container exited (1)"), those newer failures only write to `StepRun.error_message` and are silently skipped. Fix-cycle agents receive the original V1–V7 table and chase the wrong problem while the current blocking failure is invisible.

In F-00067 S17 this caused 3 fix cycles and 12 failed runs before the step passed; fix-cycle prompts 2 and 3 still showed the run-1 `ENV_DATA_MISSING` report while runs 2–4 and 6 were failing with a dashboard container crash.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. The fix lives entirely in `orch/daemon/fix_cycle.py`. No DB schema changes, no frontend changes.

## Steps to Reproduce

1. Run a browser-verification step that calls `iw step-fail` with a report (e.g., `ENV_DATA_MISSING: ...`). This sets `WorkflowStep.report_file` and `WorkflowStep.report_content`.
2. Fix cycle 1 is triggered. The fix agent makes changes.
3. The daemon relaunches the E2E stack and runs the step again. This run fails for a *different* reason (e.g., dashboard container crashes — the daemon records the error in `StepRun.error_message` directly, without calling `iw step-fail`).
4. Fix cycle 2 is triggered.
5. Observe that fix-cycle 2's prompt contains the original run-1 report, not the newer "browser env setup failed" error.

**Expected**: Fix cycle 2 prompt includes the most recent failed `StepRun.error_message` as the primary failure context, with the original V table as secondary context.

**Actual**: Fix cycle 2 prompt contains identical content to fix-cycle 1 — the run-1 failure report — because `step.report_file` is still set from run 1 and `_get_browser_findings` never reaches the `latest_run.error_message` fallback.

## Root Cause Analysis

`_get_browser_findings` (`orch/daemon/fix_cycle.py:589–623`) has a strict priority order:

1. Read `step.report_file` from disk (line 597) → **always succeeds if `iw step-fail` was ever called**
2. Fall back to `step.report_content` (line 604)
3. Last resort: query latest failed `StepRun.error_message` (line 607)

`step.report_file` is written by `iw step-fail` (see `orch/cli/step_commands.py:431`) on the first agent-reported failure and is **never cleared or updated** between fix cycles. Daemon-detected failures (container crash, stall timeout, env setup failure) write only to `StepRun.error_message`, not to `step.report_file`. So the "last resort" query at line 607 is dead code whenever an agent has previously called `iw step-fail`.

The fix must check whether a more recent failed `StepRun` exists beyond the one that set `step.report_file`, and if so, surface that run's `error_message` as the **leading context** in the returned findings string — while preserving the V table from the original report as background.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Fix cycle prompt builder | `orch/daemon/fix_cycle.py:_get_browser_findings` | Returns stale report; newer failures invisible to fix agent |
| Fix cycle prompt builder | `orch/daemon/fix_cycle.py:attempt_fix_cycle` | Calls `_get_browser_findings`; propagates stale data |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Fix `_get_browser_findings` to detect and surface newer failed StepRuns | — |
| S02 | CodeReview_Backend | Review S01 | — |
| S03 | Tests | Write reproduction test + regression tests | — |
| S04 | CodeReview_Tests | Review S03 | — |
| S05 | CodeReview_Final | Global review of all work | — |
| S06 | QvGate lint | `make lint` | — |
| S07 | QvGate format | `make format-check` | — |
| S08 | QvGate typecheck | `make typecheck` | — |
| S09 | QvGate unit-tests | `make test-unit` | — |
| S10 | QvGate integration-tests | `make allure-integration` | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — reads only existing `StepRun` rows

### Code Changes

- **Files to modify**: `orch/daemon/fix_cycle.py` (function `_get_browser_findings`)
- **Nature of change**: After reading `step.report_file` / `step.report_content`, query the latest failed `StepRun` for this step. If its `run_number` corresponds to a run that has no `report_file` (i.e., a daemon-detected failure) OR its `error_message` differs from what was in the original report, prepend a `## ⚠️ Most Recent Failure (run N)` section with the newer `error_message` before the original report content.

The simplest correct approach:
```python
# After reading the report (step.report_file / step.report_content):
latest_failed = db.execute(
    select(StepRun)
    .where(StepRun.step_id == step.id,
           StepRun.status.in_([RunStatus.failed, RunStatus.timeout]))
    .order_by(StepRun.run_number.desc())
    .limit(1)
).scalar_one_or_none()

if latest_failed and latest_failed.error_message:
    # Check if the latest run has no agent report (daemon-detected failure)
    if not latest_failed.report_file:
        content = (
            f"## ⚠️ Most Recent Failure (run {latest_failed.run_number})\n\n"
            f"{latest_failed.error_message}\n\n"
            "---\n\n"
            "## Original Browser Report (run 1 — V table context)\n\n"
            + content
        )
```

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00050_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00050_S01_Backend_prompt.md` | Prompt | Fix `_get_browser_findings` |
| `prompts/I-00050_S02_CodeReview_Backend_prompt.md` | Prompt | Review S01 |
| `prompts/I-00050_S03_Tests_prompt.md` | Prompt | Reproduction + regression tests |
| `prompts/I-00050_S04_CodeReview_Tests_prompt.md` | Prompt | Review S03 |
| `prompts/I-00050_S05_CodeReview_Final_prompt.md` | Prompt | Global cross-layer review |

## Test to Reproduce

```python
def test_i00050_get_browser_findings_returns_latest_run_error(
    db_session, test_project
):
    """_get_browser_findings must surface newer daemon-detected failures,
    not only the report from the first iw step-fail call.

    This test FAILS before the fix (returns only the original report)
    and PASSES after the fix (prepends the latest run's error).
    """
    # Arrange: create a browser_verification step
    step = WorkflowStep(...)  # browser_verification type

    # Run 1: agent calls iw step-fail with a report (ENV_DATA_MISSING)
    run1 = StepRun(run_number=1, status=RunStatus.failed,
                   error_message="ENV_DATA_MISSING: no callouts in DB",
                   report_file="reports/I-00050_S01_BV_report.md")
    step.report_file = "reports/I-00050_S01_BV_report.md"
    step.report_content = "## V1 FAIL\n..."

    # Run 2: daemon records a container crash (no report_file on StepRun)
    run2 = StepRun(run_number=2, status=RunStatus.failed,
                   error_message="browser env setup failed: e2e-dashboard-1 exited (1)",
                   report_file=None)

    # Act
    findings = _get_browser_findings(db_session, step, "/tmp/worktree")

    # Assert: latest run's error is PRESENT and LEADS the findings
    assert "browser env setup failed" in findings
    assert "e2e-dashboard-1 exited (1)" in findings
    assert findings.index("browser env setup failed") < findings.index("V1 FAIL"), \
        "Latest run error must appear before the stale V table"
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given a browser-verification step that has report_file set from run 1 (agent-reported failure)
AND a later StepRun (run 2+) with a different error_message but no report_file (daemon-detected)
When _get_browser_findings is called for this step
Then the returned string leads with the latest run's error_message
 AND still contains the original V table as secondary context
```

### AC2: Regression test exists

```
Given the fix is applied
When make test-unit and make allure-integration run
Then the reproduction test passes
 AND no existing fix_cycle tests regress
```

### AC3: No change when latest run is the same as original report run

```
Given a browser-verification step where the latest failed StepRun has report_file set
(i.e., agent called iw step-fail — no newer daemon-detected failure)
When _get_browser_findings is called
Then the output is identical to pre-fix behaviour (original report returned unchanged)
```

## Regression Prevention

- The integration test in `tests/integration/test_fix_cycle.py` should cover the multi-run scenario (run 1 agent-reported, run 2 daemon-detected).
- The unit test in `tests/unit/test_fix_cycle.py` can mock the DB query to verify the prepend logic without a container.
- Add a note in `_get_browser_findings`'s docstring that `step.report_file` is always run 1's snapshot and newer failures must be sourced from `StepRun`.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Reproducing test**: Integration test with two `StepRun` rows (run 1 with report_file, run 2 without); assert latest error leads the output.
- **Unit tests**: Mock the DB to return `latest_failed` with no `report_file`; assert prefix is prepended. Also test the no-op case (latest run has `report_file` — original behaviour preserved).
- **Integration tests**: Full `_get_browser_findings` call via testcontainer; verify exact string ordering.

## Notes

- The `_get_browser_findings` docstring should be updated to describe the new behaviour.
- The `_get_review_findings` function (line 543) has its own "last resort" fallback; it is not affected because it is used for code-review and QV steps, not browser-verification steps. Only `_get_browser_findings` is in scope.
- Do not change `_latest_failure_reason` — it is used separately for the `prior_failure_reason` / ENV_DATA_MISSING suspicion block and is already correct.
