# I-00113_S01_Backend_prompt

**Work Item**: I-00113 -- Re-review StepRun marked PID-dead immediately after fix-cycle commit, burning fix-cycle budget
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures spun up by pytest are exempt; nothing else.

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migrations.

## Input Files

- `ai-dev/active/I-00113/I-00113_Issue_Design.md` — Design document, authoritative.
- `orch/daemon/fix_cycle.py` — `_launch_fix_agent` (~line 2400+) and `_build_fix_launch_argv` (~line 2266).
- `orch/daemon/step_monitor.py` — `_check_step_health` (~205), `_is_pid_alive` (~181), `_handle_crashed` (~261).
- `orch/daemon/batch_manager.py` — step launch path (search for `pid_alive=True`).
- `.worktrees/CR-00082/ai-dev/logs/CR-00082_S04_run{2,4,6,8,10}.log` — empty/banner-only PID-dead samples.
- `tests/unit/daemon/test_step_monitor*.py` (if it exists), `tests/unit/test_fix_cycle.py` — existing test surface.

## Output Files

- `ai-dev/active/I-00113/reports/I-00113_S01_Backend_report.md` — required, structured.
- Modified files: `orch/daemon/fix_cycle.py` and/or `orch/daemon/step_monitor.py` (LOGGING/INSTRUMENTATION ONLY — see Constraints).
- New file(s): a focused unit-test that deterministically reproduces the PID-dead-without-work pattern (place under `tests/unit/daemon/`).

## Context

A non-trivial fraction (~36% in the CR-00082 S04 sample on 2026-05-25) of re-launched review StepRuns are flagged failed with `"Process exited without reporting completion (PID dead)"` within a poll cycle or two of being spawned, before the agent has produced any output. Each failure consumes a fix-cycle slot, eventually pushing the step past its 5-cycle cap.

The leading hypothesis (Issue Design, "Root Cause Analysis"): the StepRun's `pid` is the launch *wrapper* PID (`script -qec ...` or `/bin/sh -c ...`), not the agent's PID. The wrapper can fork its child, exec it, and exit quickly; `/proc/<wrapper-pid>` then disappears, and the daemon's next poll cycle's `_is_pid_alive` returns False → `_handle_crashed` marks the run failed. The real agent is alive but orphaned.

S01's job is to verify or refute this hypothesis, NOT to fix it. The fix is S03's job, gated on S01's findings.

## Requirements

1. **Instrument** the spawn → poll → PID-check path. Add structured logging covering:
   - Wrapper PID and (where possible) child PID at spawn time.
   - Wrapper exit observation, with timestamp delta from spawn.
   - Every `_is_pid_alive` call's result, with timestamp delta from `started_at` and the path probed.
   - The `_handle_crashed` event with the same delta.
   These logs must use `logger.info`/`logger.debug` at appropriate levels — they're a permanent diagnostic aid, not a temporary `print`.

2. **Build a deterministic reproduction test** under `tests/unit/daemon/`. The test must:
   - Construct a fake "fast-exit wrapper" — a real `subprocess.Popen` of a shell one-liner that prints a banner, optionally writes a child PID, then exits within ~10 ms. The wrapper command must not require external state (no DB, no testcontainer).
   - Wait a short, bounded interval (e.g. up to 200 ms) for the wrapper to exit.
   - Call the daemon's poll path (`_check_step_health` or a thin wrapper around `_is_pid_alive` + `_handle_crashed`).
   - Assert it observes the failure mode: a `StepRun`-equivalent object is flagged failed despite no real agent crash. Place the assertion on the EXACT condition the bug exhibits.
   - The RED-first principle applies: this test must FAIL against current `main` (proving the bug) once the assertion is inverted from "bug observed" to "bug fixed". S01 writes the test in BUG-OBSERVED form (test passes today, will fail after S03 fix). S04 will own the final assertion direction.

3. **Produce a written RCA** in the S01 report covering:
   - **Hypothesis status**: confirmed / refuted / partially confirmed, with evidence.
   - **Evidence**: log excerpts, PID values observed at each stage, timing measurements.
   - **Adjacent rule-ins/rule-outs** (every one must be addressed):
     - Is the failure wrapper-specific (`script -qec` vs `/bin/sh -c`)? Measure both.
     - Does fix-cycle commit duration correlate with the failure rate? Cross-reference DB timestamps.
     - Is there a race between `db.commit()` after StepRun insert and the poll loop's read?
     - Is `_is_pid_alive` itself buggy (e.g., the /proc fallback at `step_monitor.py:200-202` returning True on non-Linux but False on Linux)?
   - **Recommended fix design** for S03 with one chosen approach (not a menu): which line(s) change, what new logic, why this approach beats alternatives. S03 implements exactly what S01 recommends.

4. **Pre-flight gates** must pass: `make lint`, `make format-check`, `make type-check`.

5. **Targeted test verification** (NOT full suites):
   - `uv run pytest tests/unit/daemon/<new-test-file>.py -v` — must pass (showing the bug exists today).
   - Do NOT run `make test-unit` or `make test-integration` — S07/S08 own those.

## Constraints

1. **NO PRODUCTION FIX in S01.** S01 may add logging/instrumentation. It may NOT change PID capture, the `_is_pid_alive` probe, `_handle_crashed`, `_max_cycles_for`, or any other code path that would alter observable behaviour besides logging.
2. **NO scope creep.** Stay inside `scope.allowed_paths`. Do not touch unrelated files in `orch/daemon/`.
3. **NO budget-logic changes.** Even if it would be tempting to exempt PID-dead runs from the fix-cycle cap — that's explicitly out of scope (see Issue Design Notes).
4. **NO `print()`** for debug output; use `logger.*` at the right level.
5. **Follow project conventions.** Read `CLAUDE.md`, `tests/CLAUDE.md`, and `orch/CLAUDE.md`.

## TDD RED Evidence

Record in the S01 report under `tdd_red_evidence`:
- The exact pytest command run.
- The output showing the test demonstrating the bug (the assertion that the StepRun was flagged failed despite a healthy agent).
- The PID/timing values observed.

This is the BUG-OBSERVED test. After S03 lands and the inversion happens in S04, the test will become BUG-FIXED.

## Result Contract

The S01 report MUST include:
- `status`: `completed` (no fix, but the step's work is done).
- `files_changed`: list of every modified/new file.
- `tdd_red_evidence`: see above.
- `rca_summary`: 5-10 line written summary of root cause + recommended fix for S03.
- `notes`: anything S03 / S04 need to know (e.g., wrapper-specific timing measurements).

## Instructions

1. Run `uv run iw step-start I-00113 --step S01` at the beginning.
2. Read the design doc and the input files listed above.
3. Add instrumentation and write the reproduction test.
4. Run the targeted pytest command; confirm RED.
5. Run pre-flight gates (`make lint`, `make format-check`, `make type-check`); all green.
6. Write the report.
7. Run `uv run iw step-done I-00113 --step S01 --report ai-dev/active/I-00113/reports/I-00113_S01_Backend_report.md` at the end.
