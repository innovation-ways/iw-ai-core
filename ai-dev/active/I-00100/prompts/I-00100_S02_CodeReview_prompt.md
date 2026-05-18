# I-00100_S02_CodeReview_prompt

**Work Item**: I-00100 — Cascade thrashing detector is dead code in the production daemon path
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. Allowed: testcontainers, read-only `docker ps` / `docker inspect`, and `./ai-core.sh` / `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step is review-only. Do not run any alembic command.

## Input Files

- `uv run iw item-status I-00100 --json`
- `ai-dev/active/I-00100/I-00100_Issue_Design.md`
- `ai-dev/active/I-00100/reports/I-00100_S01_Backend_report.md`
- All files listed in S01's `files_changed` (expected: `orch/daemon/fix_cycle.py`)

## Output Files

- `ai-dev/active/I-00100/reports/I-00100_S02_CodeReview_report.md`

## Context

S01 was a pure plumbing fix that should thread `project_config` through `check_active_fix_cycles` → `_check_fix_cycle_health` → `_complete_fix_cycle` so the guard at `fix_cycle.py:1139` (`if potential_reset_ids and project_config is not None:`) can run and the existing `_detect_thrashing` function becomes reachable from production.

The bug, and the exact lines, are documented in the design's **Root Cause Analysis** section. Use that as your spec — the implementation either matches it or it doesn't.

## Read the Design Document FIRST

Before opening the diff:
- Read the **Root Cause Analysis** section in full. It names every line that should change.
- Read **Affected Components** and **AC3** (no behaviour change for non-thrashing cases) — the fix is supposed to be invisible when thrashing is not happening.
- Note that S03 (tests-impl) is responsible for the regression test. S01 is not expected to add behavioural tests; its `tdd_red_evidence` should be `"n/a — pure plumbing fix; behavioural regression test added in S03"`.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

If either reports new violations on `orch/daemon/fix_cycle.py`, file each as a CRITICAL finding with `"category": "conventions"`. Pay particular attention to ruff `ARG001` — the whole point of S01 is to remove a now-incorrect `# noqa: ARG001` annotation. If ruff now flags `project_config` as unused, the plumbing fix is wrong (the parameter must actually reach the guard).

## Review Checklist

### 1. The plumbing actually reaches the guard

For each of these specific call sites, verify the parameter is now threaded:

| Call site | Before | After (expected) |
|-----------|--------|------------------|
| `check_active_fix_cycles` signature | `project_config: ProjectConfig, # noqa: ARG001` | `project_config: ProjectConfig` (no noqa) |
| Loop body `_check_fix_cycle_health(...)` call | `(db, cycle, project_id)` | `(db, cycle, project_id, project_config)` |
| `_check_fix_cycle_health` signature | `(db, cycle, project_id)` | `(db, cycle, project_id, project_config: ProjectConfig)` |
| Internal `_complete_fix_cycle(...)` call | `(db, cycle, project_id, now)` | `(db, cycle, project_id, now, project_config=project_config)` (or positional 5th arg, either is fine) |

If any of these is missing, the fix is incomplete — flag as CRITICAL.

### 2. Nothing else was touched

This is a surgical fix. Flag any other modifications to `orch/daemon/fix_cycle.py` as CRITICAL — in particular:
- Changes to `_detect_thrashing` (line 956 region)
- Changes to `_cascade_reset_upstream_qv_gates` (line 869 region)
- Changes to the `cascade_thrashing_detected` event emission (line 1160 region)
- Signature changes to `_complete_fix_cycle` beyond what's needed (the default `project_config=None` must stay so existing unit-test callers still work)
- Drive-by refactors, renames, formatting changes outside the touched lines

### 3. No sibling regressions in the call chain

Look for other callers of `_check_fix_cycle_health` and `_complete_fix_cycle` (e.g. timeout/kill paths inside `_check_fix_cycle_health` that bypass the PID-dead branch, or test-only callers). If S01 broke them by adding a positional argument without a default at the wrong place, flag as CRITICAL.

### 4. The noqa removal is justified

Ruff `ARG001` will now examine `project_config` and `config` in `check_active_fix_cycles`. After S01:
- `project_config` should be used (passed into the next call) — ruff should NOT flag it.
- `config` (the `DaemonConfig` second argument) was also previously `# noqa: ARG001`. S01 was NOT asked to remove that one (it's still unused on this seam). If S01 removed it AND propagated `config` further: not in scope, flag as HIGH (out-of-scope edit). If S01 left it alone: correct.

### 5. Tests are unchanged

S01 should not have modified any test file. If `files_changed` includes a test file, flag as HIGH and document which test was changed and why.

### 6. Project conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Verify imports and types follow the SQLAlchemy 2.0 + sync `Session` + dataclass `ProjectConfig` pattern already used elsewhere in `fix_cycle.py`.

## TDD RED Evidence

S01 is a behaviour-implementing step BUT the design explicitly defers the behavioural test to S03 (tests-impl). The expected `tdd_red_evidence` is the `"n/a — <reason>"` form. Verify the report says exactly that or close to it; if S01 invented a behavioural test of its own under `tests/unit/daemon/`, flag as MEDIUM_FIXABLE (the test belongs in S03's scope).

## Test Verification

Run the targeted unit tests for the daemon's fix-cycle module:

```bash
uv run pytest tests/unit/daemon/ -v -k "thrashing or fix_cycle"
```

Report pass/fail. Full-suite execution is the QV gates' job — don't run it here.

## Severity Levels

Use the standard scale: CRITICAL, HIGH, MEDIUM_FIXABLE, MEDIUM_SUGGESTION, LOW. Only CRITICAL / HIGH / MEDIUM_FIXABLE trigger a fix cycle.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00100",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "orch/daemon/fix_cycle.py",
      "line": 0,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
