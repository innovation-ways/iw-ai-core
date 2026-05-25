# I-00113: Re-review StepRun marked PID-dead immediately after fix-cycle commit, burning fix-cycle budget

**Type**: Issue
**Severity**: High
**Created**: 2026-05-25
**Reported By**: Operator (diagnosed during CR-00082 S04 review thrash on 2026-05-25)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This incident adds NO alembic migrations — daemon process-management fix only.

## Description

After a fix-cycle completes, the daemon launches a fresh review `StepRun` for the same step. In a non-trivial fraction of cases that re-launched run is marked `failed` with `"Process exited without reporting completion (PID dead)"` within one or two daemon poll cycles, before the agent had any opportunity to do work. Each occurrence consumes one of the per-step fix-cycle budget slots (`_DEFAULT_FIX_CYCLE_MAX = 5`), so a step that should converge in 2–3 real fix attempts can exhaust its budget and stall instead.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Particularly relevant for this incident:

- The daemon is a single-threaded polling loop (`orch/daemon/main.py`) that polls every 60 s and uses `_is_pid_alive()` to track running StepRuns (`orch/daemon/step_monitor.py:181`).
- Step launches are wrapped — opencode runs are wrapped under `script -qec` for PTY allocation; other CLI tools run under `/bin/sh -c` (`orch/daemon/fix_cycle.py:_build_fix_launch_argv`, line ~2266). The `proc.pid` recorded on the StepRun is the wrapper's PID, not the agent's PID.
- Fix-cycle creation is in `orch/daemon/fix_cycle.py:_launch_fix_agent` (around line 2471) — it records `pid=proc.pid` and `pid_alive=True` on a fresh StepRun and commits.
- `tests/CLAUDE.md` is the canonical guide for test placement; daemon-spawn tests belong under `tests/unit/daemon/` or `tests/integration/daemon/`.

## Steps to Reproduce

Reproduction is timing-dependent; the observable signal is in the database. The 2026-05-25 sample comes from CR-00082 S04:

1. Approve any work item whose review step (e.g. `code-review-impl`) will fail at least twice in a row.
2. Watch `step_runs` for the failing step: `SELECT run_number, status, error_message, started_at FROM step_runs sr JOIN workflow_steps ws ON sr.step_id=ws.id WHERE ws.work_item_id='<ITEM>' AND ws.step_id='<STEP>' ORDER BY run_number`.
3. Observe runs alternate between two patterns:
   - Odd runs (1, 3, 5, …) report real findings and fail with a substantive `error_message`.
   - Even runs (2, 4, 6, …), which start within seconds of the preceding fix-cycle commit, fail with `error_message = "Process exited without reporting completion (PID dead)"` and have no log content beyond a startup banner.

**Expected**: Every re-launched review StepRun runs the agent to completion (either pass or substantive fail) before being marked terminal. PID-dead detection should fire only when the agent process really has died — never on a process the daemon spawned in the same poll cycle.

**Actual**: A fraction of re-launched re-review StepRuns (4 of 11 in the CR-00082 S04 sample on 2026-05-25) are marked failed within one or two poll cycles with `"Process exited without reporting completion (PID dead)"`, even though no agent work happened. Each one consumes a fix-cycle slot, pushing the step past its 5-cycle cap.

## Root Cause Analysis

**TBD — requires investigation. S01 owns the diagnosis.**

The leading hypothesis to test in S01:

The `proc.pid` recorded at line `orch/daemon/fix_cycle.py:2475` is the PID of the *launch wrapper* (`script -qec ...` for opencode, `/bin/sh -c ...` for other CLIs). The wrapper can fork its child, exec it, and exit quickly; once the wrapper exits, `/proc/<wrapper-pid>` disappears. The next daemon poll cycle calls `_is_pid_alive(run.pid)` (`orch/daemon/step_monitor.py:214`) which checks `/proc/<wrapper-pid>` and sees it gone → `_handle_crashed` marks the StepRun failed with `"Process exited without reporting completion (PID dead)"` (`step_monitor.py:269-273`). The actual agent process is alive — but orphaned from the daemon's view.

Possible adjacent contributors S01 must rule in or out:

- The fix-cycle commit itself (the `git commit` issued by the executor between agent runs) may stall the parent shell long enough for the wrapper to die before the agent inherits stdin/stdout cleanly.
- `script -qec` vs `sh -c` may have different fork/exit timings; the failure may be wrapper-specific.
- A race between `db.commit()` after StepRun insert (`fix_cycle.py:2489`) and the daemon's poll loop reading the same StepRun.
- 4 of 11 (≈36 %) failure rate is too high for a pure race; there may be a systematic timing issue tied to fix-cycle commit duration.

S01 must produce a written RCA in the S01 report covering: which hypothesis is correct, evidence (logs, traces, repro), and a recommended fix design.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/fix_cycle.py:_launch_fix_agent` (~2471) | Records wrapper PID instead of agent PID; this is the proximate source of the wrong PID. |
| `orch/daemon/step_monitor.py:_check_step_health` (~205) | Polls `_is_pid_alive(run.pid)`; flags the StepRun failed without grace period for newly-spawned runs. |
| `orch/daemon/step_monitor.py:_handle_crashed` (~261) | Writes `"Process exited without reporting completion (PID dead)"` and consumes a fix-cycle slot. |
| `orch/daemon/fix_cycle.py:_max_cycles_for` (~351) | Counts the resulting failed `FixCycle` rows toward the per-step cap, blocking legitimate further retries. |

## Fix Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. See `skills/iw-workflow/SKILL.md`.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Instrument & reproduce. Add structured logging around StepRun spawn, wrapper-exit, and the next poll cycle's PID check. Build a focused unit test that replays spawn→poll→`_is_pid_alive` against a fast-exit wrapper shim to deterministically reproduce the PID-dead-without-work pattern. Produce a written root-cause analysis in the S01 report (`ai-dev/active/I-00113/reports/I-00113_S01_Backend_report.md`) covering hypothesis verification, evidence, and recommended fix design. **NO production fix in this step.** | — |
| S02 | code-review-impl | Per-agent review of S01: instrumentation correctness, no production behaviour changed, repro test actually demonstrates the failure mode, RCA quality. | — |
| S03 | backend-impl | Apply the fix recommended by S01's RCA. Likely candidates (S01 decides): (a) capture the *real* agent PID rather than the wrapper PID (e.g. via the wrapper writing the child PID to a sidecar file, or by using `Popen` with `start_new_session=True` and tracking the process group); (b) add a settle/grace period for newly-spawned StepRuns where one /proc miss within N seconds of `started_at` is treated as transient; (c) detect wrapper-style launches and probe `/proc` for any descendant before declaring crash. Implement exactly one approach, justified by S01's evidence. | — |
| S04 | tests-impl | Reproduction test (lift the S01 repro into a permanent test under `tests/unit/daemon/` or `tests/integration/daemon/`) + regression tests over the full spawn→monitor lifecycle (wrapper-exit, real agent crash, real agent slow start, real agent timeout — every branch must still be covered). | — |
| S05 | code-review-impl | Per-agent review of S03 + S04. | — |
| S06 | code-review-final-impl | Global cross-agent review (AC1–AC4). | — |
| S07..S14 | qv-gate | lint / format / typecheck / assertions / unit-tests / integration-tests / diff-coverage / security-secrets | — |
| S15 | self-assess-impl | Self-assessment via `iw-item-analyze`. | — |

Total: 15 steps. `browser_verification: false`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no alembic changes

### Code Changes

- **Files to modify**:
  - `orch/daemon/fix_cycle.py` — `_launch_fix_agent` (around line 2471). PID-capture logic and/or logging.
  - `orch/daemon/step_monitor.py` — `_check_step_health` / `_handle_crashed` (around lines 205, 261). PID-alive probe and/or grace-period logic.
  - `tests/unit/daemon/test_fix_cycle.py` (or new sibling) — reproduction + regression coverage.
  - `tests/integration/daemon/test_fix_cycle.py` (if integration-level reproduction is required).
- **Nature of change**: targeted fix to the spawn/monitor lifecycle so newly-spawned StepRuns are not flagged crashed before the agent has had a chance to register.

## File Manifest

All files for this work item live under `ai-dev/active/I-00113/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00113_Issue_Design.md` | Design | This document |
| `I-00113_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator (14 steps; `browser_verification: false`) |
| `prompts/I-00113_S01_Backend_prompt.md` | Prompt | S01 — instrument + reproduce + RCA |
| `prompts/I-00113_S02_CodeReview_prompt.md` | Prompt | S02 — review of S01 |
| `prompts/I-00113_S03_Backend_prompt.md` | Prompt | S03 — apply fix (gated by S01 RCA) |
| `prompts/I-00113_S04_Tests_prompt.md` | Prompt | S04 — reproduction + regression tests |
| `prompts/I-00113_S05_CodeReview_prompt.md` | Prompt | S05 — review of S03 + S04 |
| `prompts/I-00113_S06_CodeReview_Final_prompt.md` | Prompt | S06 — global cross-agent review |
| `prompts/I-00113_S15_SelfAssess_prompt.md` | Prompt | S15 — self-assessment |

Reports are created during execution under `ai-dev/work/I-00113/reports/`.

## Test to Reproduce

Write a failing test that demonstrates the bug before fixing it.

**Test-file location** — Daemon-spawn tests belong under `tests/unit/daemon/` or `tests/integration/daemon/`. A unit-level repro is preferred (deterministic, no real subprocess). Use a fake wrapper subprocess (e.g. a shell one-liner that exits immediately after writing a child PID) and an injectable `_is_pid_alive` to drive the timing.

```python
def test_i_00113_reproduces_pid_dead_after_fix_cycle_commit():
    """This test should FAIL before the fix and PASS after.

    Reproduces the daemon's premature PID-dead detection on a freshly-
    spawned StepRun whose launch wrapper exits before the daemon's first
    poll. Asserts the StepRun is NOT marked failed and the fix-cycle
    counter is NOT incremented.
    """
    # Arrange: spawn a fake fast-exit wrapper that simulates the script -qec
    # behaviour (parent forks, exits quickly).
    # Act: call the daemon poll loop's _check_step_health once with the
    # wrapper PID.
    # Assert: StepRun.status is still RunStatus.running (NOT failed); error
    # message is None; no _handle_crashed event was emitted.
```

## Acceptance Criteria

### AC1: Reproduction test exists and proves the bug pre-fix

```
Given the project at the commit BEFORE this incident's fix
When `uv run pytest tests/unit/daemon/test_<repro>.py::test_i_00113_reproduces_pid_dead_after_fix_cycle_commit -v` is run
Then the test FAILS
And the failure message names the wrong-PID-dead detection as the cause
```

### AC2: Bug is fixed

```
Given the fix from S03 has shipped
When `uv run pytest tests/unit/daemon/test_<repro>.py -v` is run
Then every test PASSES
And no StepRun is marked failed within the configured grace window when
    its wrapper exits but a real agent child has been registered
```

### AC3: Regression tests cover every branch of the spawn→monitor lifecycle

```
Given S04 has shipped
When `tests/unit/daemon/test_<repro>.py` is read
Then it contains separate test cases for at least:
    - wrapper exits fast, real agent is alive (must NOT mark failed — this is the bug)
    - wrapper exits, no real agent registered (must mark failed — true crash)
    - real agent is alive and producing output (must NOT mark failed — happy path)
    - real agent timeout (must mark failed by timeout, not by PID-dead)
```

### AC4: No false-positive PID-dead in production telemetry over a 24-hour observation window

```
Given the fix has been deployed and the daemon has been running for 24 hours
When `SELECT run_number, error_message FROM step_runs WHERE error_message LIKE '%PID dead%' AND started_at > NOW() - INTERVAL '24 hours'` is executed
Then every returned row corresponds to a StepRun that ran for > grace_window_seconds before being flagged
And no row exists where started_at and completed_at are within the grace window
```

## Regression Prevention

- **Reproduction test under `tests/unit/daemon/`** keeps the bug from silently regressing — the fake-fast-exit-wrapper case becomes a permanent invariant.
- **Structured logging from S01** stays in production after the fix so future PID-dead occurrences are traceable end-to-end (wrapper-pid, child-pid, /proc-state-at-poll-N) without manual log archaeology.
- **Audit table query in AC4** can be wired to a recurring daemon-events alert if the failure mode returns under different conditions.

## Dependencies

- **Depends on**: None — the diagnosis is self-contained; the fix touches only daemon process-management code.
- **Blocks**: None directly. Adjacent: it WILL prevent CR-00082 / future review-step thrashing from exhausting their fix-cycle budget via this specific failure mode.

## Impacted Paths

```
orch/daemon/fix_cycle.py
orch/daemon/step_monitor.py
tests/unit/daemon/**
tests/integration/daemon/**
ai-dev/active/I-00113/**
```

No production code outside `orch/daemon/`. No migrations.

## TDD Approach

- **Reproducing test**: S01 builds the deterministic unit-level repro using a fake fast-exit wrapper shim and an injectable `_is_pid_alive`. The RED run lives in S01's report under `tdd_red_evidence`.
- **Unit tests**: S04 lifts S01's repro and expands it to cover every spawn→monitor branch (see AC3).
- **Integration tests**: only if S01's RCA concludes a real subprocess is needed (e.g. `script -qec`-specific timing). If a deterministic unit-level repro is sufficient, S04 stays unit-only.
- **Updated tests**: none expected — existing tests under `tests/unit/daemon/test_step_monitor*.py` and `tests/integration/daemon/test_fix_cycle*.py` must still pass.

## Notes

- **Why investigation-first?** The hypothesis (wrong PID captured at spawn) is strong but not proven. Skipping S01 and going straight to a fix risks correcting the wrong layer (e.g., adding a grace period when the real bug is wrapper PID capture) and either masking the issue or introducing a new race. S01's report locks the diagnosis before any production line is changed.
- **Why no migration / no API / no Frontend?** This is purely a daemon-side process-management bug. No persisted schema, no HTTP contract, no UI.
- **Observed sample (CR-00082 S04, 2026-05-25)**: 4 of 11 StepRuns reported PID-dead within seconds of being spawned. Logs at `.worktrees/CR-00082/ai-dev/logs/CR-00082_S04_run{2,4,6,8,10}.log` are empty beyond a startup banner; DB rows show `error_message = "Process exited without reporting completion (PID dead)"`.
- **Out of scope**: changes to how fix-cycles count toward the per-step cap (e.g., exempting PID-dead-on-spawn from the budget). The right fix is to stop generating false PID-dead rows in the first place; budget logic stays untouched.
