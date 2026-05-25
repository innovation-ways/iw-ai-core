# I-00113_S03_Backend_prompt

**Work Item**: I-00113 -- Re-review StepRun marked PID-dead immediately after fix-cycle commit
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits
Standard policy.

## ⛔ Migrations: agents generate, daemon applies
No migrations.

## Input Files

- `ai-dev/active/I-00113/I-00113_Issue_Design.md` — design document.
- `ai-dev/active/I-00113/reports/I-00113_S01_Backend_report.md` — S01's RCA. **S03 implements the fix approach S01 recommended, no other.**
- `ai-dev/active/I-00113/reports/I-00113_S02_CodeReview_report.md` — S02's review of S01.
- `orch/daemon/fix_cycle.py`, `orch/daemon/step_monitor.py`.

## Output Files

- `ai-dev/active/I-00113/reports/I-00113_S03_Backend_report.md`
- Modified daemon files per S01's recommendation.

## Context

S01 confirmed the root cause and recommended ONE fix approach. S03's job is to implement that approach exactly — not to second-guess it, and not to bundle in an alternative. If S03 discovers S01's recommendation is wrong or incomplete, STOP and report under `blockers`; do NOT silently swap in a different fix.

## Requirements

1. **Read S01's report first.** The `rca_summary` and `recommended_fix` sections define the contract for this step.

2. **Implement the recommended fix.** The likely surface is one or more of:
   - `orch/daemon/fix_cycle.py:_launch_fix_agent` (~line 2400+) — PID capture.
   - `orch/daemon/step_monitor.py:_check_step_health` (~205) — first-poll grace period.
   - `orch/daemon/step_monitor.py:_is_pid_alive` (~181) — probe semantics.

   S01 picked ONE of these. Implement it.

3. **Preserve every existing branch of the spawn→monitor lifecycle:**
   - Real agent alive + producing output → still tracked, heartbeat updated.
   - Real agent crashes mid-run → still marked failed via `_handle_crashed`.
   - Timeout → still fires via the timeout branch (not the PID-dead branch).
   - Stall (heartbeat too old) → still fires.

   The bug branch (wrapper-exit before child is registered) is the ONLY one whose behaviour changes.

4. **Update or delete S01's instrumentation only if S01's report explicitly says it should change.** Otherwise leave the logging in — it's a permanent diagnostic.

5. **Update the reproduction test** so it now asserts the BUG-FIXED state (no more false PID-dead). S04 will own additional regression coverage; S03 owns flipping the assertion direction on S01's test.

6. **Pre-flight gates** must pass: `make lint`, `make format-check`, `make type-check`.

7. **Post-edit gate** (per the project's new fix-prompt convention): after your last edit, run `make format-check` and `make lint`. Resolve any new violations before exiting.

8. **Targeted verification only:**
   - `uv run pytest tests/unit/daemon/<repro-test>.py -v` — must pass (BUG-FIXED).
   - `uv run pytest tests/unit/daemon/ -v --no-cov` — must pass (no regression to adjacent tests).
   - Do NOT run `make test-unit` or `make test-integration` — S07/S08 own those.

## Constraints

1. **Implement S01's recommended approach only.** No alternative-fix bundling. If S01's recommendation cannot be implemented as described, STOP and write `blockers` in the report; do not improvise.
2. **NO budget-logic changes.** `_max_cycles_for` and the fix-cycle count remain untouched. The right fix is to stop generating false failures, not to exempt them from the cap.
3. **Stay inside `scope.allowed_paths`.**
4. **No new alembic migration.**
5. **Follow project conventions.** Read `CLAUDE.md`, `orch/CLAUDE.md`, `tests/CLAUDE.md`.

## TDD Evidence

S01 owned the RED. S03 owns the GREEN:
- Record in the report under `tdd_green_evidence` the targeted pytest run showing the test now passes after the fix.
- Quote the diff of the assertion-direction flip (single-line change in the repro test).

## Result Contract

The S03 report MUST include:
- `status`: `completed`.
- `files_changed`: every modified file.
- `tdd_green_evidence`: see above.
- `lifecycle_branches_audited`: a short table confirming each of the 4 branches in Requirements #3 still works (with evidence — test name + result).
- `notes`: anything S04 / S05 / S06 need.

## Instructions

1. `uv run iw step-start I-00113 --step S03`.
2. Read S01's report, the design doc, and the relevant daemon source.
3. Implement the fix per S01's recommendation.
4. Flip the repro test assertion to BUG-FIXED.
5. Pre-flight + post-edit gates green.
6. Targeted verification green.
7. Write the report.
8. `uv run iw step-done I-00113 --step S03 --report ai-dev/active/I-00113/reports/I-00113_S03_Backend_report.md`.
