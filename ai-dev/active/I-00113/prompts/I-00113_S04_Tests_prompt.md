# I-00113_S04_Tests_prompt

**Work Item**: I-00113 -- Re-review StepRun marked PID-dead immediately after fix-cycle commit
**Step**: S04
**Agent**: tests-impl

---

## ⛔ Docker is off-limits
Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies
No migrations.

## Input Files

- `ai-dev/active/I-00113/I-00113_Issue_Design.md` — design document. Read the Acceptance Criteria section (especially AC3) carefully.
- `ai-dev/active/I-00113/reports/I-00113_S01_Backend_report.md` — S01's RCA + repro test.
- `ai-dev/active/I-00113/reports/I-00113_S03_Backend_report.md` — S03's fix + the BUG-FIXED reproduction.
- The fix implementation in `orch/daemon/fix_cycle.py` and/or `orch/daemon/step_monitor.py`.

## Output Files

- `ai-dev/active/I-00113/reports/I-00113_S04_Tests_report.md`
- New/expanded test file(s) under `tests/unit/daemon/` (and optionally `tests/integration/daemon/`).

## Context

S01 added a reproduction test that proved the bug existed. S03 flipped its assertion direction once the fix landed. S04 expands coverage so every branch of the spawn→monitor lifecycle has explicit regression protection. The goal is that no future refactor can re-introduce the bug or silently weaken adjacent correctness.

## Requirements

1. **Reproduction test (canonical).** Keep S01's repro test under `tests/unit/daemon/` as the canonical regression for THIS bug. S04 may rename it for clarity but must preserve the semantics (a fast-exit wrapper + a healthy "agent" → daemon must NOT mark the run failed within the grace window).

2. **Branch coverage (AC3 from the design doc).** Add test cases (in the SAME file or a sibling) covering every spawn→monitor branch:
   - **Wrapper-exit + healthy agent** (the bug case): MUST NOT mark failed within the grace window. — S01 already wrote this.
   - **Wrapper-exit + no agent registered** (true crash on spawn): MUST mark failed (after grace window). The error message MUST be `"Process exited without reporting completion (PID dead)"` or the explicit "No PID recorded" variant if the post-fix code path uses that.
   - **Agent alive + producing output** (happy path): MUST NOT mark failed; `last_heartbeat` updates; `pid_alive` stays True.
   - **Agent timeout**: MUST mark failed via the TIMEOUT branch (with `error_message` reflecting timeout), NOT via PID-dead. The two error messages must NOT be conflated.
   - **Agent stall (heartbeat too old)**: MUST mark failed via the HARD-STALL branch (after `> stall_threshold * 2`), NOT via PID-dead.

3. **Property of correctness** — assert behaviour, not implementation:
   - For each branch, assert ONE specific observable outcome (StepRun.status, StepRun.error_message containing a substring, count of `_handle_crashed` calls, etc.) — not "any of these is fine".
   - For the bug case (wrapper-exit + healthy agent), assert the StepRun status is `running` (NOT failed) AND that `_handle_crashed` was NOT called.

4. **Semantic correctness over shape checking** (mandatory):

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this incident, that translates to:
- BAD: `assert run.status != RunStatus.running` (anything that isn't running passes — too weak)
- BAD: `assert run.error_message is not None` (any error message passes)
- GOOD: `assert run.status is RunStatus.failed` AND `assert "PID dead" in (run.error_message or "")` (specific terminal state + specific message)
- GOOD: `assert _handle_crashed_calls == 0` (specific count, not just "low")

5. **No mocking the database.** Daemon unit tests should not touch the DB at all — operate on in-memory `StepRun`-shaped objects or use the existing daemon-unit fixtures.

6. **No mocking subprocesses where realistic spawning is feasible.** Use real `subprocess.Popen` of fast shell one-liners for the wrapper-exit cases (deterministic and faithful). Pure mocks of `_is_pid_alive` are acceptable ONLY for the timeout/stall branches that don't need a real process.

7. **Targeted verification only** (per project's I-00073 lesson):
   - `uv run pytest tests/unit/daemon/<your-files>.py -v` — must pass.
   - Do NOT run `make test-integration` or `make test-unit` — S08/S07 own those. Duplicating full-suite runs in this step burns the timeout budget.

8. **Pre-flight gates** must pass: `make lint`, `make format-check`, `make type-check`.

9. **Post-edit gate**: run `make format-check` and `make lint` before exiting; resolve any new violations introduced by your edits.

## Constraints

1. **No revert-style RED-check at runtime.** Do NOT `git checkout HEAD~1 -- orch/...` or `git stash` to "prove the test would catch the bug pre-fix" — that's a design-time exercise, already done by S01. Such operations are thrash-prone.
2. **No production-code edits.** S04 is tests-only; if you find a real defect, raise it as a `blockers` entry in the report and do not patch it.
3. **No new alembic migration.**
4. **Stay inside `scope.allowed_paths`.**
5. **Follow project conventions.** Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md`.

## TDD RED Evidence (deferred)

S04 is a test-coverage step, not a behaviour-implementing step. Record `tdd_red_evidence` as:

```
n/a — coverage step; behaviour RED was owned by S01 (see I-00113_S01_Backend_report.md)
```

## Result Contract

The S04 report MUST include:
- `status`: `completed`.
- `files_changed`: every new/modified test file.
- `branches_covered`: bulleted table mapping each AC3 branch to the test name(s) that cover it.
- `targeted_test_evidence`: pytest output for the new tests, showing all pass.

## Instructions

1. `uv run iw step-start I-00113 --step S04`.
2. Read S01 + S03 reports, the design's AC3, and the fix implementation.
3. Expand coverage to all 5 branches in Requirements #2.
4. Targeted test verification green.
5. Pre-flight + post-edit gates green.
6. Write the report.
7. `uv run iw step-done I-00113 --step S04 --report ai-dev/active/I-00113/reports/I-00113_S04_Tests_report.md`.
