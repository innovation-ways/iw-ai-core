# I-00100_S04_CodeReview_prompt

**Work Item**: I-00100 — Cascade thrashing detector is dead code in the production daemon path
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers via pytest fixtures are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step is review-only. No alembic commands.

## Input Files

- `uv run iw item-status I-00100 --json`
- `ai-dev/active/I-00100/I-00100_Issue_Design.md`
- `ai-dev/active/I-00100/reports/I-00100_S03_Tests_report.md`
- `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py` (the new file from S03)
- `orch/daemon/fix_cycle.py` (post-S01 state)
- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` — testing rules and red-flag checklist

## Output Files

- `ai-dev/active/I-00100/reports/I-00100_S04_CodeReview_report.md`

## Context

S03 wrote an integration test that drives the production seam `check_active_fix_cycles` → `_check_fix_cycle_health` → `_complete_fix_cycle` to prove the cascade thrashing detector is now wired in. Your job is to verify the test is **strong** — not just present.

The single most likely failure mode here is a "shape-checking" test that would pass even against pre-S01 code. Hunt for it.

## Read the Design Document FIRST

- Read **Test to Reproduce**, **AC1**, **AC2**, **AC3** in full.
- Read the design's **Regression Prevention** section — the test is supposed to be the regression net.
- Note that AC3 ("no behaviour change for non-thrashing cases") REQUIRES a negative-control test. If S03 only wrote the positive case, that's a HIGH finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

If either flags `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py`, file each new violation as a CRITICAL conventions finding.

## Review Checklist

### 1. The test drives the PRODUCTION seam, not the leaf function

Open the test file. Verify the act phase calls **`fix_cycle.check_active_fix_cycles(...)`** at the top of the daemon's call chain. If the test instead calls `_complete_fix_cycle(...)` directly, `_detect_thrashing(...)` directly, or `_check_fix_cycle_health(...)` directly:

- That is a CRITICAL finding. Such a test is unable to catch the bug this incident exists to fix; it could have passed even against pre-S01 code.

### 2. Assertions are semantic, not shape

For every `assert` in the test, ask: "If I delete the line in production code that this is supposed to cover, does this assertion fail?"

Examples of the failure mode to flag (CRITICAL):
- `assert events` — non-empty check, doesn't tell you what's in `events`
- `assert "cascade_thrashing_detected" in str(events)` — substring on stringification
- `assert event.event_type` — truthiness, not equality
- `assert "trigger_step_id" in event.event_metadata` — key-presence, not value

Examples of acceptable assertions:
- `assert event.event_type == "cascade_thrashing_detected"`
- `assert event.event_metadata["trigger_step_id"] == "S02"`
- `assert event.event_metadata["cascade_count"] == 3`
- `assert set(event.event_metadata["reset_set"]) == {"S01"}`
- `assert upstream_step.status == StepStatus.completed`

### 3. The negative-control test exists and works

Verify the file contains **both** of these tests (names may vary but the intent must match):

1. Positive: 3 same-trigger overlapping cascades → detector fires, upstream gate is NOT reset.
2. Negative: 3 same-trigger non-overlapping cascades → detector does NOT fire, upstream gate IS reset.

Without the negative case, the test cannot defend AC3.

### 4. Dead-PID setup is sound

The test depends on `_is_pid_alive(pid)` returning `False` so `_check_fix_cycle_health` takes the "PID dead → complete cycle" branch. Verify S03's chosen approach:

- Using a fork-then-reap pattern: acceptable, but document that on Linux a recycled PID could theoretically be alive again — usually fine for a short-lived test, but flag MEDIUM_FIXABLE if the test is flaky-prone.
- Monkeypatching `_is_pid_alive` to return `False`: acceptable and most robust.
- Hardcoding a PID like `999999` and hoping it's dead: NOT acceptable — flag as HIGH.

### 5. Test isolation

- Each test uses a fresh `db_session` (the per-test template-clone).
- No cross-test state leakage (the second test must not assume rows inserted by the first).
- Run the file with `-p randomly --randomly-seed=12345` and confirm both pass in either order. Report the seed in your `notes`.

### 6. Targeted run only, no full-suite invocation

The test file must NOT shell out to `make test-integration` or otherwise expand its scope. Flag any such invocation as HIGH.

### 7. Test placement and naming

- File path: `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py` (per design's File Manifest). If S03 placed it elsewhere, flag as MEDIUM_FIXABLE and ask for relocation.
- Function names start with `test_` and describe behaviour (positive case names what fires, negative names what doesn't).
- Docstrings explain *why* the test would have failed pre-S01 (the RED reasoning).

### 8. Touched files

S03 should have created exactly one new file and modified zero existing files. If `files_changed` includes anything other than the new test file:
- Modifications to `orch/daemon/fix_cycle.py` → CRITICAL (S03 is not allowed to touch production code).
- Modifications to other test files → HIGH unless justified in the report's notes.
- Touched `conftest.py` to add a helper fixture → MEDIUM_FIXABLE; verify the helper is genuinely shared and not single-use.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/daemon/test_cascade_thrashing_detector_wiring.py -v
```

Both tests must pass. Report the exact pass/fail counts.

## Severity Levels

Standard scale. CRITICAL / HIGH / MEDIUM_FIXABLE trigger a fix cycle.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00100",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "tests/integration/daemon/test_cascade_thrashing_detector_wiring.py",
      "line": 0,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": "Include the randomly-seed used to confirm order-independence."
}
```
