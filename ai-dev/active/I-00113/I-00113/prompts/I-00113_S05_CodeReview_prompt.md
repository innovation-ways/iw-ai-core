# I-00113_S05_CodeReview_prompt

**Work Item**: I-00113 -- Re-review StepRun marked PID-dead immediately after fix-cycle commit
**Steps Being Reviewed**: S03 (fix) + S04 (tests)
**Review Step**: S05
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits
Standard policy.

## ⛔ Migrations: agents generate, daemon applies
No migrations expected.

## Input Files

- `ai-dev/active/I-00113/I-00113_Issue_Design.md` — design document (Acceptance Criteria are mandatory checks).
- `ai-dev/active/I-00113/reports/I-00113_S01_Backend_report.md` — S01's RCA (the recommended-fix contract S03 was bound to).
- `ai-dev/active/I-00113/reports/I-00113_S03_Backend_report.md` — fix report.
- `ai-dev/active/I-00113/reports/I-00113_S04_Tests_report.md` — tests report.
- All files in those reports' `files_changed`.
- Daemon source: `orch/daemon/fix_cycle.py`, `orch/daemon/step_monitor.py`.

## Output Files

- `ai-dev/active/I-00113/reports/I-00113_S05_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations in S03+S04 changed files → CRITICAL.

## Scope Discipline — Implicitly Allowed Paths

The daemon implicitly allows `ai-dev/active/I-00113/**`, `ai-dev/archive/I-00113/**`, `ai-dev/work/I-00113/**`. Do NOT flag those.

## Review Checklist

### 1. Fix correctness vs S01's recommendation (CRITICAL findings)

- The diff in `orch/daemon/fix_cycle.py` / `orch/daemon/step_monitor.py` MUST match the approach S01 recommended in its `rca_summary` / `recommended_fix`.
- If S03 implemented something different from S01's recommendation (e.g., S01 said "grace window", S03 wrote "wrapper-PID capture"), that is CRITICAL — the chain is supposed to be linear.
- Exception: if S03's report explicitly documents a blocker AND why the alternate approach was necessary, it's HIGH (not CRITICAL) — but the blocker chain must be auditable.

### 2. Lifecycle-branch preservation (AC3 — CRITICAL findings)

For each of the 5 branches in S04's coverage matrix, verify:
- Wrapper-exit + healthy agent → NOT marked failed (the fixed branch).
- Wrapper-exit + no agent → STILL marked failed (true crash). Error message MUST be substring-correct.
- Agent alive + heartbeating → still tracked, heartbeat updates.
- Timeout → fires via timeout branch, NOT via PID-dead.
- Stall → fires via hard-stall branch, NOT via PID-dead.

Missing branch → CRITICAL. Branch tested but with weak assertion (e.g. `status != running` instead of `status is failed`) → HIGH.

### 3. Test quality (HIGH findings, semantic correctness)

- Tests assert specific observable values, not shape (see Tests prompt's mandatory warning).
- No test mocks the database.
- No test does runtime `git checkout` / `git stash` to "prove the bug".
- Tests run deterministically — no `time.sleep` > 200 ms, no flake-prone polling without a timeout.

### 4. No budget-logic changes (CRITICAL)

- `_max_cycles_for`, `check_active_fix_cycles`, and `FixCycle` count handling are UNCHANGED. The fix targets PID detection, not the budget. Any change there is CRITICAL — out of scope per the design.

### 5. No production code outside daemon module (CRITICAL)

- Diff against main MUST touch only `orch/daemon/fix_cycle.py`, `orch/daemon/step_monitor.py`, `tests/unit/daemon/**`, `tests/integration/daemon/**`, `ai-dev/active/I-00113/**`.
- Any file under `orch/db/`, `dashboard/`, `executor/`, `scripts/`, `bin/`, `orch/db/migrations/versions/**` is CRITICAL scope creep.

### 6. RED→GREEN audit trail intact

- S01's report has `tdd_red_evidence` showing the bug pre-fix.
- S03's report has `tdd_green_evidence` showing the same test post-fix.
- The test name in both reports matches.
- The assertion-direction flip is visible in the diff and is a small focused change.

### 7. Logging / instrumentation

- S01's logging is still in place (or S03's report explicitly justified removing it).
- No `print()` statements introduced.
- Log lines include enough context (step_id, item_id, PID values) to debug recurrence.

### 8. Test convention compliance

- Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md`.
- Tests follow assertion-strength rules.
- Test file placement is correct (`tests/unit/daemon/` for pure unit, `tests/integration/daemon/` only if a real subprocess/DB is needed).

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/daemon/ -v --no-cov
uv run pytest tests/integration/daemon/ -v --no-cov   # ONLY if S04 added integration tests
make lint
make format-check
make type-check
```

Do NOT run the full unit/integration suites — S07/S08 own those.

## Severity Levels

Standard CRITICAL/HIGH/MEDIUM/LOW rubric. Default any deviation from S01's recommendation to CRITICAL (the chain is contract-bound).

## Result Contract

Standard review report. End with:

```bash
uv run iw step-done I-00113 --step S05 --report ai-dev/active/I-00113/reports/I-00113_S05_CodeReview_report.md
```

(or `step-fail` if the verdict is fail).
