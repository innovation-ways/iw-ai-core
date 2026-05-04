# I-00063_S02_CodeReview_Backend_prompt

**Work Item**: I-00063 — Daemon Phase 2 migration apply self-deadlocks against its own idle-in-transaction session
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

(Standard policy. Read-only introspection commands like `docker ps`,
`docker inspect`, `docker logs` are allowed for diagnosis. Touching
container/volume/network state is forbidden.)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This issue does NOT add or modify any migration. If S01 added one,
flag it as a CRITICAL finding — they were instructed not to.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00063 --json`
- `ai-dev/active/I-00063/I-00063_Issue_Design.md` — Design document
- `ai-dev/active/I-00063/reports/I-00063_S01_Backend_report.md` — S01 report
- All files in `S01_Backend_report.json:files_changed`

## Output Files

- `ai-dev/active/I-00063/reports/I-00063_S02_CodeReview_report.md` — Review report

## Context

You are reviewing the backend fix for I-00063 self-deadlock. The
design doc's Acceptance Criteria (AC1-AC5) and Root Cause Analysis
sections are the authoritative spec — read them first. Then read the
S01 report and the changed files.

The fix is intentionally small. Watch for over-engineering: the goal
is to commit-and-close `db` before `run_post_merge_apply()`, set a
lock_timeout, and add a self-blocker check. Anything beyond that
is scope creep.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run:

```bash
make lint
make format
```

If either reports NEW violations in S01's `files_changed`, classify
each as a **CRITICAL** finding with `"category": "conventions"`.
If a tool is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. AC1 — `_merge_item` session lifecycle

- Is `db.commit()` followed by `db.close()` invoked **before**
  `run_post_merge_apply(batch_item.batch_id)` at the original
  line 290?
- Are all post-apply uses of `db` in `_merge_item` either (a)
  re-opened via a fresh `SessionLocal()` (recommended) or (b)
  re-bound after the apply call?
- Does the existing `except` block at the original line 319 still
  receive a usable session? Trace the post-fix code path with the
  S01 report's `notes` to confirm.
- **CRITICAL** if `db` is closed and then later used without
  reopening — that's a `DetachedInstanceError` waiting to ship.

### 2. AC3 — `lock_timeout` on the apply connection

- Is `SET lock_timeout = '<N>s'` actually run on the **alembic
  apply** connection (not on the lock-acquisition connection)?
  Trace the engine wiring:
  `apply()` → `_build_alembic_config` → `command.upgrade` →
  alembic's internal `EnvironmentContext`.
- Does the env var `IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS` work?
  Default 30s. `0` disables. Negative values must be rejected
  (or normalized — pick one and verify).
- Is the timeout applied **before** any DDL runs? If alembic opens
  a connection lazily, the `SET` may need to be on a `connect`
  event listener, not at config build time.
- **HIGH** if the SET runs on the wrong connection. **HIGH** if the
  env var is silently ignored. **MEDIUM** if the value is set but
  never observed in tests.

### 3. AC4 — Self-blocker detection

- Is `SelfBlockerError` (or the chosen exception) raised **before**
  `command.upgrade()` runs, when a same-process blocker is detected?
- What signal does the implementation use? Acceptable options:
  `application_name` matching, `pg_blocking_pids` + process tree,
  comparing `client_addr`+`client_port`+parent PID. Document trade-
  offs in the review notes.
- Is the error message useful — does it name the blocking PID and
  the relation, or does it just say "blocked"? **MEDIUM** if the
  message is unactionable.
- Is the detection robust against false positives? E.g. another
  daemon process running locally (an integration test) shouldn't
  cause a real apply to fail. **HIGH** if it does.

### 4. AC5 — `pending_migration_log` captures failures

- Trace the failure path: when `SelfBlockerError` is raised inside
  `apply()`, does the existing `except Exception as exc` handler at
  `safe_migrate.py:563` catch it and write a row to
  `pending_migration_log` with `success=false` and a useful
  `error_message`?
- Same question for `lock_timeout` failures.

### 5. Code quality and convention compliance

- Sync SQLAlchemy 2.0 patterns. No async sneaking in.
- psycopg v3, not psycopg2. URL replacement done correctly.
- `DaemonEvent.event_metadata` (Python) ↔ `metadata` (SQL column).
- Logger names match `__name__` per file.
- New exception classes have docstrings.
- New env var follows existing config pattern (consult
  `orch/config.py`).
- No dead code, no commented-out blocks, no stale TODOs.

### 6. Scope compliance

- S01 was instructed NOT to write tests (S03's job). If S01
  contributed tests, it's not necessarily a finding — additive
  unit tests near the fix are encouraged. But:
  - **HIGH** if S01 added a "reproduction" test that duplicates S03's
    upcoming work.
  - **HIGH** if S01 modified files outside the design doc's
    Impacted Paths list.
  - **CRITICAL** if S01 added a migration.

### 7. Project conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Confirm:

- Layer boundaries respected (no `dashboard/` imports from `orch/`,
  no `orch.daemon` imports from `orch.db`).
- Naming matches existing daemon code (snake_case, no Hungarian).
- New env var added to `.env.example` if project has one.

### 8. Security

- No hardcoded credentials.
- No SQL injection risk in the self-blocker check (use parameterised
  queries via SQLAlchemy `text()` with bind params, not f-strings).
- `lock_timeout` value parsed safely from env (no shell injection
  via `SET lock_timeout = '<N>s'` if `<N>` is operator-controlled —
  validate as int).

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `make test-unit` — confirm S01 didn't regress unit tests.
2. Run `make test-integration` — same.
3. Report results in the contract.

Do not run S03's reproduction test (it doesn't exist yet). Note its
absence as a "deferred to S03" reminder.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks fix, breaks daemon, security vuln, scope creep (e.g. unauthorised migration) | Must fix before merge |
| **HIGH** | Bug in fix, AC not met, fragile self-blocker check, lock_timeout on wrong connection | Must fix before merge |
| **MEDIUM_FIXABLE** | Convention violation, weak error message, missing env-var documentation | Should fix in fix cycle |
| **MEDIUM_SUGGESTION** | Better pattern available, slightly nicer naming | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00063",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": "Reviewer's evaluation of the trade-off choices documented in S01's notes (reopen-vs-refactor, lock_timeout wiring, self-blocker signal). State whether the choices are sound or whether a fix-cycle should revisit them."
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
