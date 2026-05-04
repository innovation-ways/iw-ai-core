# I-00063_S04_CodeReview_Tests_prompt

**Work Item**: I-00063 — Daemon Phase 2 migration apply self-deadlocks against its own idle-in-transaction session
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures spun up by pytest are exempt.)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. Tests may run alembic against testcontainer URLs only.)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00063 --json`
- `ai-dev/active/I-00063/I-00063_Issue_Design.md` — Design (Acceptance Criteria, TDD Approach)
- `ai-dev/active/I-00063/reports/I-00063_S03_Tests_report.md` — S03 report, including TDD verification evidence
- All test files in S03's `files_changed`
- `tests/CLAUDE.md` — test patterns
- S01 + S02 reports (for context on which detection mechanism the implementation uses)

## Output Files

- `ai-dev/active/I-00063/reports/I-00063_S04_CodeReview_report.md` — Review report

## Context

You are reviewing the test coverage for I-00063. The reproduction test
is the load-bearing artifact — if it doesn't actually catch the bug,
the entire incident package is theatre. Verify it does.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run:

```bash
make lint
make format
```

If either reports NEW violations in S03's `files_changed`, classify
each as a **CRITICAL** finding with `"category": "conventions"`.

## Review Checklist

### 1. Reproduction test correctness (load-bearing)

- Does the reproduction test actually exercise the bug? Read it
  carefully. The test must:
  - Open an outer session and acquire a real `AccessShareLock` on the
    target table (not a mocked one).
  - Invoke `safe_migrate.apply` against a real testcontainer with a
    pending DDL that takes `AccessExclusiveLock`.
  - Run with a finite timeout so a regression surfaces as a test
    failure, not a hung suite.
  - Assert specifically what changed (success, or
    `SelfBlockerError`, or `lock_timeout` — not just "didn't hang").
- Did S03 perform the TDD verification dance (stash → fail →
  unstash → pass)? Look for `tdd_red_green_verified: true` in the
  S03 report and quoted pytest output. **CRITICAL** if missing.
- If the reproduction test relies on a synthetic test-only migration,
  is that migration in a tests-only `versions/` directory (not
  modifying the real chain)? **CRITICAL** if the real migration chain
  was modified.

### 2. Semantic correctness over shape (I003 lesson)

Re-read the I003 warning in the S03 prompt. Then audit every
assertion in the new tests. **HIGH** finding for any assertion that:

- Only checks a key exists (`assert "x" in data`).
- Only checks a non-empty container (`assert len(data) > 0`).
- Only checks `is not None`.
- Only checks the type of a value rather than its value.

These are not necessarily wrong on their own — a sequence of
shape-then-value checks is fine — but a test consisting only of
shape checks is a bug masquerading as coverage.

### 3. Test isolation and determinism

- Each test cleans up its testcontainer state. No cross-test
  contamination.
- Outer sessions are always closed in a `finally` (otherwise a
  failed test leaks the lock and contaminates subsequent tests).
- No `time.sleep(...)` longer than ~5s — those slow CI without
  buying anything.
- `pytest.mark.timeout` is set on tests that could hang on regression.
- No reliance on wall clock or system timezone.

### 4. Test coverage vs ACs

Map each AC to at least one test:

| AC | Tested by |
|----|-----------|
| AC1: no self-deadlock end-to-end | `test_phase2_apply_no_self_deadlock`, plus session-lifecycle test, plus the rollback-fires-after-failure test (S03 §6) |
| AC2: regression test exists | The reproduction test itself |
| AC3: `lock_timeout` set | `test_lock_timeout_*` tests |
| AC4: self-blocker detection | `test_self_blocker_*` tests |
| AC5: `pending_migration_log` audit | `test_pending_migration_log_*` tests |

**HIGH** finding for any unmapped AC.

### 4a. Rollback-after-failure coverage (AC1 end-to-end)

S03 §6 requires a test that exercises the apply-fails → rollback-fires
transition through `_merge_item` (or its closest entry point). Confirm:

- A test exists that forces apply to fail (via synthetic blocker or
  monkeypatched `safe_migrate.apply` returning `success=False`).
- The test asserts `run_rollback` was invoked with the correct
  `batch_id` (spy/monkeypatch).
- The test asserts the post-apply `_emit_event(... "migration_pipeline" ...)`
  call uses a **fresh session** — proving S01's session-discipline fix
  did not silently break the failure path's bookkeeping.
- The test asserts the daemon does not hang.

**HIGH** finding if the rollback transition is not tested at all.
**MEDIUM_FIXABLE** if it's tested but doesn't verify the fresh-session
property (that's the regression most likely to ship undetected).

### 5. Test quality

- Names describe what they verify (`test_apply_raises_self_blocker_when_…`,
  not `test_1`).
- Setup is in fixtures, not duplicated across tests.
- Each test has a single clear purpose.
- Failure messages on assertions are useful for debugging
  (`assert x == y, f"expected y, got {x}"` style where appropriate).

### 6. Project conventions (read `tests/CLAUDE.md`)

- Testcontainer URL replacement done correctly:
  `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- No `importlib.reload(orch.config)` — `monkeypatch.delenv` instead.
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` run after `create_all()` if
  any test does FTS.
- `event_metadata` (Python) ↔ `metadata` (column).
- No live-DB connections (port 5433).

### 7. Test runtime budget

- `make test-integration` already takes time. New tests should
  collectively add no more than ~30s on a clean run.
- The reproduction test's timeout should be 60s (per design); reject
  anything wildly higher.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `make test-unit` — must pass.
2. Run `make test-integration` — must pass.
3. Spot-check the reproduction test by running it in isolation:
   `uv run pytest tests/integration/daemon/test_phase2_apply_no_self_deadlock.py -v`.
4. If you have time, replicate S03's TDD verification: stash S01's
   diff, run the reproduction test, confirm it fails. (Optional —
   note in your report whether you did or didn't.)

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Reproduction test doesn't catch the bug; real migration chain modified; TDD red-green not verified | Must fix before merge |
| **HIGH** | AC unmapped to tests; shape-only assertions; test isolation broken | Must fix before merge |
| **MEDIUM_FIXABLE** | Convention violation, weak failure messages, slow test | Should fix in fix cycle |
| **MEDIUM_SUGGESTION** | Better fixture available, slightly nicer naming | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00063",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "testing|code_quality|conventions",
      "file": "tests/...",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "ac_coverage_map": {
    "AC1": ["test_..."],
    "AC2": ["test_..."],
    "AC3": ["test_..."],
    "AC4": ["test_..."],
    "AC5": ["test_..."]
  },
  "notes": "Whether the reviewer independently verified TDD red-green; any AC with weak coverage."
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE.
- `ac_coverage_map`: explicit mapping of each AC to test names. An AC
  with an empty list is automatically a CRITICAL finding.
