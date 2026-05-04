# I-00063_S05_CodeReview_Final_prompt

**Work Item**: I-00063 — Daemon Phase 2 migration apply self-deadlocks against its own idle-in-transaction session
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures are exempt; read-only
introspection (`docker ps`, `inspect`, `logs`) is allowed.)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This issue does not add or modify any migration; if
S01 added one, it is a CRITICAL finding.)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00063 --json`
- `ai-dev/active/I-00063/I-00063_Issue_Design.md` — Design
- `ai-dev/active/I-00063/I-00063_Functional.md` — Functional design
- All implementation reports: `ai-dev/active/I-00063/reports/I-00063_S0[1-4]_*_report.md`
- All per-agent review reports
- All files listed in all implementation reports' `files_changed`

## Output Files

- `ai-dev/active/I-00063/reports/I-00063_S05_CodeReview_Final_report.md` — Final review report

## Context

You are performing the final cross-cutting review of the I-00063 fix
package. Per-agent reviews (S02, S04) have looked at backend code and
tests in isolation; your job is to evaluate them as one fix.

The whole fix is small. That's intentional. Watch for the opposite
failure mode: a backend fix that's correct in isolation but doesn't
actually compose with the tests' execution model. For example: S01
might claim to set `lock_timeout` via a `connect` event listener, and
S03's test might verify the env var via a different code path that
doesn't go through that listener. Both pass per-agent review; the fix
ships broken.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

CRITICAL on any new violations in any of S01-S04's `files_changed`.

## Review Checklist

### 1. Completeness vs Design Document

For each section of `I-00063_Issue_Design.md`, confirm there is
corresponding code or evidence:

| Section | Expected artifact | Reviewer check |
|---------|-------------------|----------------|
| Description / Root Cause Analysis | — | Read; understand the deadlock chain |
| Steps to Reproduce | reproduction test | S03's test exercises the same chain |
| Affected Components | code changes in `merge_queue.py`, `safe_migrate.py` | S01 modified those files |
| Fix Plan | S01-S05 + QV gates | Manifest matches |
| Test to Reproduce | `test_phase2_apply_no_self_deadlock.py` | Exists and passes |
| AC1..AC5 | tests + code | All five mapped |
| Regression Prevention | code + tests | Session discipline + lock_timeout + self-blocker check + reproduction test all in place |
| Impacted Paths | manifest `scope.allowed_paths` | Match exactly |

**CRITICAL** for any missing piece.

### 2. Cross-step consistency

- The exception class S01 raises matches what S03 catches. (E.g. if
  S01 named it `SelfBlockerError`, S03's tests import the same
  symbol.)
- The env var name S01 reads matches what S03 sets via
  `monkeypatch.setenv`.
- The default `lock_timeout` value (30s) matches across S01 (default
  in code) and S03 (the assertion).
- The `application_name` strings (if used as the self-blocker signal)
  match across S01 and S03's blocking-session setup.

### 3. Integration points

- Does `_merge_item`'s post-fix flow actually compose with
  `run_post_merge_apply`'s self-blocker check? Trace it: the daemon
  commits and closes `db`, the apply opens its own connection, the
  self-blocker check runs against `pg_stat_activity` — at this point
  the daemon has zero idle-in-transaction connections, so the check
  passes. Confirmed?
- If `_merge_item` ever needs `db` after the apply (e.g. to write
  the `migration_pipeline` failure event), is the fresh session
  opened, used, committed, and closed correctly?
- Does `_emit_event` still work as documented ("caller commits") in
  every call site, or did S01 accidentally change its semantics?
- Does the new `_assert_no_self_blockers` query work on PostgreSQL
  15 (the project's testcontainer image)? `pg_blocking_pids` exists
  since PG 9.6 so this should be safe; verify.

### 4. Test coverage (holistic)

- Read S04's `ac_coverage_map`. Each AC has at least one test?
- Are there cross-cutting scenarios not covered by either S01-side or
  S03-side tests in isolation? E.g.:
  - The fix-cycle path: a Phase 2 failure (`SelfBlockerError`)
    triggers `run_rollback`. Is the rollback path tested too? If
    not, **MEDIUM_FIXABLE** — the rollback path is downstream of
    the failure mode.
  - The `merge_queue_frozen` flag: if rollback fails after a
    self-blocker abort, does the queue freeze correctly? Tested?
- Are happy-path regressions covered? If the fix accidentally broke
  a normal Phase 2 apply (no blocker, no timeout needed), is there
  a test that catches that?

### 5. Architecture compliance

Read `CLAUDE.md` and `orch/CLAUDE.md`.

- Layer boundaries respected. `orch.daemon.merge_queue` should not
  import from `dashboard/`. `orch.db.safe_migrate` should not import
  from `orch.daemon`.
- Sync SQLAlchemy 2.0 throughout — no async leaks.
- psycopg v3, not psycopg2.
- `event_metadata` (Python) ↔ `metadata` (column).

### 6. Security (cross-cutting)

- The new env var `IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS` is parsed
  safely. No `int()` without try/except, no injection via
  `f"SET lock_timeout = '{val}s'"` if `val` is unsanitised.
- The self-blocker query uses parameterised SQL (`text(...)` with
  bind params), not string interpolation.
- Error messages do not leak credentials. The DB URL is sometimes
  formatted into log lines; verify the new error paths sanitise it.

### 7. Documentation

- Was `orch/CLAUDE.md` updated if the daemon's session-lifecycle
  contract changed materially? (Not strictly required for an
  internal refactor of one function, but if the docstring of
  `_emit_event` or the comments in `_merge_item` no longer match
  reality, fix or flag.)
- Was `docs/IW_AI_Core_Daemon_Design.md` updated to mention the new
  defensive `lock_timeout` and self-blocker check? Optional but
  preferred — flag as MEDIUM_SUGGESTION if missing.

### 8. Functional design alignment

Read `I-00063_Functional.md`. Does the implemented behavior match the
"How It Behaves" section? Specifically:

- "Routine batch merges that include a database schema change no
  longer freeze the daemon or the dashboard." — verifiable via the
  reproduction test.
- "If a migration cannot acquire its database lock within thirty
  seconds (or whatever value the operator has configured), it fails
  fast with a clear error in the daemon log instead of hanging
  silently." — verifiable via the lock_timeout test.
- "The audit trail captures every failed apply attempt with a
  useful error message." — verifiable via the
  `pending_migration_log` test.

If any user-facing claim in the functional doc is not actually true
of the implemented code, **HIGH** finding — the user-facing
documentation is wrong.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run **the full test suite**:
   ```bash
   make test-unit
   make test-integration
   ```
2. Run the reproduction test in isolation and quote pytest output in
   your report.
3. Run `make typecheck` over the whole project. If it reports new
   errors NOT in the files S01/S03 changed, those are pre-existing —
   note them but don't fail S05 over them.
4. If integration tests fail, this is a CRITICAL finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Missing AC mapping, reproduction test doesn't catch the bug, real migration chain modified, integration tests fail, security regression | Must fix before merge |
| **HIGH** | Cross-step inconsistency (mismatched symbol names, env vars, etc.), functional doc claims something the code doesn't do, missing rollback-path coverage | Must fix before merge |
| **MEDIUM_FIXABLE** | Convention violation, weak error messages, missing happy-path regression test | Should fix in fix cycle |
| **MEDIUM_SUGGESTION** | Daemon design doc not updated, slightly nicer pattern available | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00063",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": "Holistic verdict on whether the fix actually closes I-00063, with quoted pytest output from the reproduction test."
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE.
- `missing_requirements`: any AC with no implementation. Each is
  automatically a CRITICAL finding.
- `cross_cutting`: set on any finding that spans S01 and S03 (e.g.
  symbol name mismatch).
