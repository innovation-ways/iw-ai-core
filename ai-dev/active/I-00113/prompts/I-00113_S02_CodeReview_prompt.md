# I-00113_S02_CodeReview_prompt

**Work Item**: I-00113 -- Re-review StepRun marked PID-dead immediately after fix-cycle commit
**Step Being Reviewed**: S01 (instrument + reproduce + RCA — no production fix)
**Review Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits
Standard policy.

## ⛔ Migrations: agents generate, daemon applies
No migrations expected from S01.

## Input Files

- `ai-dev/active/I-00113/I-00113_Issue_Design.md` — design document, authoritative.
- `ai-dev/active/I-00113/reports/I-00113_S01_Backend_report.md` — S01's report (must exist).
- All files listed in S01 report's `files_changed`.
- Daemon source: `orch/daemon/fix_cycle.py`, `orch/daemon/step_monitor.py`.

## Output Files

- `ai-dev/active/I-00113/reports/I-00113_S02_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations in S01's changed files → CRITICAL finding.

## Scope Discipline — Implicitly Allowed Paths

When checking the diff vs main, remember the daemon also implicitly allows:
- `ai-dev/active/I-00113/**`
- `ai-dev/archive/I-00113/**`
- `ai-dev/work/I-00113/**`

Do NOT flag those as scope creep.

## Review Checklist

### 1. Scope discipline (CRITICAL findings)

- Diff against main MUST touch only paths inside `scope.allowed_paths`: `orch/daemon/fix_cycle.py`, `orch/daemon/step_monitor.py`, `tests/unit/daemon/**`, `ai-dev/active/I-00113/**`. Any file under `orch/db/`, `dashboard/`, `executor/`, `scripts/`, `bin/`, or `orch/db/migrations/versions/**` is CRITICAL.

### 2. No production behaviour change (S01's hard constraint — CRITICAL findings)

- S01 may add logging only. The DIFF in `orch/daemon/fix_cycle.py` and `orch/daemon/step_monitor.py` MUST consist of `logger.*` additions, parameter passing for context (`step_id`, etc.), and trivial supporting code. Any change to:
  - PID capture (`pid=proc.pid` line),
  - `_is_pid_alive` logic,
  - `_handle_crashed` write path,
  - `_max_cycles_for` budget logic,
  is CRITICAL — S01 was explicitly forbidden from fixing anything.
- Search the diff for `if` / `else` / `return` / state mutations that aren't pure logging — any match is suspect.

### 3. Reproduction test exists and shows the bug today

- Test file under `tests/unit/daemon/`.
- Uses a real `subprocess.Popen` with a fast-exit shell command (not pure mock of `_is_pid_alive` — the bug must be observable, not stipulated).
- Asserts the BUG-OBSERVED state (StepRun flagged failed despite agent being healthy).
- Runs deterministically (no `time.sleep(<long>)`, no flake-prone wait).
- Targeted-test run is GREEN: `uv run pytest tests/unit/daemon/<new-test>.py -v` exits 0.

### 4. RCA quality

The S01 report `rca_summary` MUST:
- Take a position: confirmed / refuted / partially confirmed (not "could be").
- Cite evidence: log excerpts, PID values, timing measurements.
- Address EVERY rule-in/rule-out in the design doc's S01 row:
  - Wrapper-specific timing (`script -qec` vs `sh -c`).
  - Fix-cycle commit duration correlation.
  - DB commit / poll-loop race.
  - `_is_pid_alive` Linux-vs-non-Linux behaviour.
- Recommend ONE fix approach for S03 with reasoning, not a menu.

A missing or shallow RCA is HIGH.

### 5. Logging quality

- Uses `logger.info` / `logger.debug` at appropriate levels — no `print()`.
- Log lines include the StepRun id and the agent's step_id for searchability.
- Sensitive content (prompt text, agent output) is NOT logged at INFO level (debug is acceptable for body content).
- No log lines added inside tight loops without sampling.

### 6. Test convention compliance

- Read `tests/CLAUDE.md`. Tests must follow assertion-strength rules.
- No mocking of the database (rule from CLAUDE.md — and unit-daemon tests don't need a DB anyway).
- Test name follows project convention.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/daemon/ -v --no-cov
make lint
make format-check
```

Do NOT run the full unit/integration suites — S07/S08 own those.

## Severity Levels

CRITICAL / HIGH / MEDIUM / LOW per the standard project rubric. Default to CRITICAL for any production-behaviour change in S01 (the step was explicitly forbidden from fixing).

## Result Contract

Standard review report contract. The report MUST set `verdict` to `pass` or `fail`, list findings with severity/category/file/line, and end with the canonical lifecycle command:

```bash
uv run iw step-done I-00113 --step S02 --report ai-dev/active/I-00113/reports/I-00113_S02_CodeReview_report.md
```

(or `step-fail` if the verdict is fail).
