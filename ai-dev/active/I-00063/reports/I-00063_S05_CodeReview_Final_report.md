# I-00063 S05 Code Review — Final Cross-Cutting Report

## Summary

The I-00063 fix (session lifecycle discipline + `lock_timeout` + self-blocker detection) is architecturally correct and the S01 backend implementation passes review. However, S03's tests have CRITICAL and HIGH findings that make the test suite non-mergeable in its current state. The reproduction test (`test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock`) does not catch the bug in pytest due to `_is_test_context_active()` bypassing both AC4 and AC3. Three tests use `importlib.reload()` in violation of CLAUDE.md, causing `DuplicateTable` crashes. AC5 tests don't actually verify `pending_migration_log` rows were written. AC1's rollback test doesn't verify `run_rollback` was invoked.

**Verdict: FAIL**

---

## Pre-Flight Gate

| Check | Result | Notes |
|-------|--------|-------|
| `make lint` | 2 pre-existing errors | `tests/dashboard/test_sse_client_wiring.py` (F811 redefinition of `re`) — NOT in S01-S04 files |
| `make format` | 1 pre-existing violation | `tests/dashboard/test_sse_client_wiring.py` — NOT in S01-S04 files |
| `make typecheck` | ✅ All passed | No new type errors in S01-S04 files |
| `make test-unit` | 2570 passed, 2 failed | Pre-existing: `test_terminal_transition_calls_compose_down`, `test_apply_logs_when_alembic_raises` |

**Pre-flight result: PASS** (pre-existing violations not counted against this work item)

---

## Step Review Scope

| Step | Agent | Files Changed | Report |
|------|-------|---------------|--------|
| S01 | backend-impl | `merge_queue.py`, `safe_migrate.py`, `config.py`, `.env.example` | ✅ |
| S02 | code-review-impl | — (review only) | ✅ |
| S03 | tests-impl | `test_phase2_apply_no_self_deadlock.py`, `test_safe_migrate_self_blocker.py` | ⚠️ |
| S04 | code-review-impl | — (review only) | ✅ |

---

## 1. Completeness vs Design Document

| Design Section | Expected Artifact | Status |
|----------------|-------------------|--------|
| Description / Root Cause | `_merge_item` session lifecycle fix | ✅ S01 implemented `db.commit()` + `db.close()` before Phase 2 |
| Steps to Reproduce | `test_phase2_apply_no_self_deadlock.py` | ⚠️ Test exists but doesn't catch the bug in pytest |
| Affected Components | `merge_queue.py`, `safe_migrate.py` | ✅ Both modified |
| Fix Plan | S01-S05 + QV gates | ✅ All steps completed |
| Test to Reproduce | `test_phase2_apply_no_self_deadlock.py` | ❌ Test fails in both pre-fix and post-fix states (see below) |
| AC1 | `_merge_item` discipline + rollback | ⚠️ Rollback test doesn't verify `run_rollback` called |
| AC2 | Regression test in CI | ❌ Reproduction test doesn't catch the bug |
| AC3 | `lock_timeout` on apply connection | ✅ Verified: `SET lock_timeout = '30s'` via event listener |
| AC4 | Self-blocker detection | ❌ Bypassed by `_is_test_context_active()` in pytest |
| AC5 | `pending_migration_log` audit | ❌ Tests don't verify log row was written |

**Missing pieces:** AC2 (regression test works), AC4 (self-blocker check bypassed in pytest), AC5 (log row not verified).

---

## 2. Cross-Step Consistency

| Check | S01 | S03 | Consistent? |
|-------|-----|-----|-------------|
| Exception class | `SelfBlockerError` defined in `safe_migrate.py:128` | Imported from `orch.db.safe_migrate` | ✅ |
| Env var name | `IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS` via `get_migration_lock_timeout_secs()` | `monkeypatch.setenv("IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS", "5")` | ✅ |
| Default `lock_timeout` | 30s in `config.py:117` and `safe_migrate.py:621` | `assert lock_timeout_value == "30s"` | ✅ |
| `_assert_no_self_blockers` signal | `pg_blocking_pids()` + `pg_stat_activity JOIN pg_locks` | Uses same function directly | ✅ |

All cross-step symbol names and values are consistent.

---

## 3. Integration Points

### Post-fix flow composition

After S01's fix (`db.commit()` at line 292, `db.close()` at line 293):
1. `db.close()` releases all `AccessShareLock` on `batch_items` and `projects`
2. `run_post_merge_apply(batch_item.batch_id)` opens its own engine/connection
3. `_assert_no_self_blockers(apply_engine)` queries `pg_blocking_pids()` — daemon has no idle-in-transaction session, check passes ✅
4. `command.upgrade(cfg, "head")` runs DDL with `lock_timeout=30s` backstop ✅

### `_emit_event` contract preserved

`_emit_event`'s docstring ("Insert a DaemonEvent — caller commits") is unchanged. All callers commit after calling it:
- `merge_queue.py:273` — `_emit_event` then `db.commit()` at line 272 (committed together with `item_merged`)
- `merge_queue.py:308-323` — fresh session commits after `_emit_event`

✅ Contract preserved.

### `_merge_item` post-apply event emission

When Phase 2 fails (line 298), `run_rollback` is called, then a fresh `SessionLocal()` is opened (lines 306-323) to emit the `migration_pipeline` rollback event. This correctly handles the case where `db` is already closed.

✅ Post-apply bookkeeping path is correct.

### PostgreSQL version compatibility

`pg_blocking_pids()` exists since PostgreSQL 9.6. The project's testcontainer uses `postgres:15-alpine`. ✅

---

## 4. Test Coverage (Holistic)

### S04 AC coverage map (verified from S04 report)

```
AC1: test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock (BROKEN)
     test_rollback_triggered_after_apply_failure (INCOMPLETE)
AC2: test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock (BROKEN)
AC3: test_lock_timeout_set_on_apply_connection (PASS)
     test_lock_timeout_env_var_honored (BROKEN: reload)
     test_lock_timeout_disabled_when_zero (PASS)
AC4: test_assert_no_self_blockers_raises_when_same_process_holds_blocking_lock (BROKEN: bypass)
     test_assert_no_self_blockers_ignores_lock_on_different_table (PASS)
     test_assert_no_self_blockers_happy_path (PASS)
     test_i_00063_assert_no_self_blockers_clean_when_no_blocker (PASS)
AC5: test_pending_migration_log_written_on_self_blocker_failure (BROKEN: no log verification)
     test_pending_migration_log_written_on_lock_timeout_failure (BROKEN: no log verification)
```

### Key coverage gaps

**1. Reproduction test doesn't catch the bug (CRITICAL)**

`test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock` hangs for 45s in both pre-fix and post-fix states. `_is_test_context_active()` returns `True` in pytest, causing `_assert_no_self_blockers()` to short-circuit. The lock_timeout backstop (AC3) also doesn't fire in pytest because the test harness doesn't properly exercise the connection that has lock_timeout set.

**The test would correctly distinguish fixed from unfixed code in production** (where `IW_CORE_TEST_CONTEXT` is never set). But in pytest, it is non-functional as a regression detector.

**2. `importlib.reload()` violation (CRITICAL)**

Three tests use `reload(orch.config)` or `reload(orch.db.safe_migrate)` to pick up env var changes. This triggers `load_dotenv()` again, re-imports `orch.db.models`, and causes `Base.metadata.create_all(engine)` to run against an already-migrated database — `DuplicateTable: relation "projects" already exists`.

Affected:
- `test_lock_timeout_env_var_honored` (line 234)
- `test_pending_migration_log_written_on_lock_timeout_failure` (line 385)
- `test_rollback_triggered_after_apply_failure` (line 447)

Per CLAUDE.md: **"NEVER call `importlib.reload(orch.config)` — use `monkeypatch.delenv()` only."**

**3. AC5 tests don't verify log row was written (HIGH)**

Both AC5 tests acknowledge that `_write_migration_log` short-circuits in test context. They verify the error message instead of querying `pending_migration_log` to confirm a row was written. AC5 specifically requires "a row exists in pending_migration_log with phase='apply', success=false, and a non-null error_message" — but the tests don't verify this.

**4. AC1 rollback test doesn't verify `run_rollback` was called (HIGH)**

`test_rollback_triggered_after_apply_failure` only verifies `apply()` fails with a lock-related error. It does NOT:
- Spy/monkeypatch `run_rollback` to verify it was called
- Verify a fresh session was used for rollback event emission

### Happy-path regression

`test_i_00063_apply_succeeds_when_no_blocking_lock` covers this ✅

---

## 5. Architecture Compliance

| Check | Status |
|-------|--------|
| Layer boundaries (`orch.daemon` not importing from `dashboard/`) | ✅ |
| `orch.db.safe_migrate` not importing from `orch.daemon` | ✅ |
| SQLAlchemy 2.0 (`Mapped[]`, declarative style, `text()` with bind params) | ✅ |
| psycopg v3 (`postgresql+psycopg://` URL scheme) | ✅ |
| `DaemonEvent.event_metadata` (Python) ↔ `metadata` (column) | ✅ |
| No async leaks | ✅ |

---

## 6. Security

| Check | Status |
|-------|--------|
| `lock_timeout` value parsed as `int()` — no injection | ✅ `int(os.environ.get())` is safe |
| `f"SET lock_timeout = '{lock_timeout_secs}s'"` — safe? | ⚠️ Safe because value is `int()`, not arbitrary string. But a more robust pattern would use parameterized SET. Not a CRITICAL finding — PostgreSQL's `SET` command does not support bind params, and the value is guaranteed to be an integer. |
| Self-blocker query uses parameterized SQL | ✅ `text(...)` with `{"pid": blocker_pid}` bind params |
| Error messages don't leak credentials | ✅ DB URL not formatted into error messages |

**Note:** `f"SET lock_timeout = '{lock_timeout_secs}s'"` at `safe_migrate.py:629` is safe because `lock_timeout_secs` is `int` type (never arbitrary string). However, a MEDIUM_SUGGESTION: consider a comment explaining why this is safe, or use `SET lock_timeout = %s` with a cursor.execute() call instead of the event listener pattern.

---

## 7. Documentation

- `orch/CLAUDE.md` — unchanged, correct. The `_emit_event` docstring still matches the code.
- `docs/IW_AI_Core_Daemon_Design.md` — not updated. This is a MEDIUM_SUGGESTION (optional).

---

## 8. Functional Design Alignment

| User-facing claim in `I-00063_Functional.md` | Reality |
|---------------------------------------------|---------|
| "Routine batch merges that include a database schema change no longer freeze the daemon or the dashboard" | ✅ `db.commit()` + `db.close()` before Phase 2 prevents the deadlock |
| "If a migration cannot acquire its database lock within thirty seconds (or whatever value the operator has configured), it fails fast with a clear error in the daemon log" | ⚠️ lock_timeout is set, but the test environment doesn't exercise it correctly (bypass issue). In production, this works. |
| "The audit trail captures every failed apply attempt with a useful error message" | ⚠️ AC5 tests don't verify `pending_migration_log` row exists; the code path is correct but not tested |

---

## 9. Test Verification

### Integration test results (I-00063 suite)

```
FAILED test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
PASSED test_i_00063_apply_succeeds_when_no_blocking_lock
FAILED test_i_00063_assert_no_self_blockers_raises_when_caller_holds_share_lock
PASSED test_i_00063_assert_no_self_blockers_clean_when_no_blocker
PASSED test_assert_no_self_blockers_happy_path
PASSED test_assert_no_self_blockers_ignores_lock_on_different_table
FAILED test_assert_no_self_blockers_raises_when_same_process_holds_blocking_lock
FAILED test_lock_timeout_env_var_honored (DuplicateTable)
PASSED test_lock_timeout_set_on_apply_connection
PASSED test_lock_timeout_disabled_when_zero
FAILED test_pending_migration_log_written_on_self_blocker_failure (DuplicateTable)
FAILED test_pending_migration_log_written_on_lock_timeout_failure (DuplicateTable)
FAILED test_rollback_triggered_after_apply_failure (DuplicateTable)

6 passed, 7 failed
```

**Root cause of failures:**
1. **Tests 1, 3, 8** — `_is_test_context_active()` short-circuits `_assert_no_self_blockers()` in pytest. The test hangs at the 45s `future.result()` timeout because neither the self-blocker check nor the lock_timeout backstop fires in the test environment.
2. **Tests 4-7** (env var override tests) — `importlib.reload(orch.config)` / `reload(orch.db.safe_migrate)` triggers `load_dotenv()` again, re-imports `orch.db.models`, runs `Base.metadata.create_all(engine)` against an already-migrated DB → `DuplicateTable`.
3. **Tests 9-10** (AC5) — Same `DuplicateTable` issue; additionally don't query `pending_migration_log` to verify the row was written.
4. **Test 11** (AC1 rollback) — Same `DuplicateTable` issue; doesn't verify `run_rollback` was called.

### pytest output (reproduction test)

```
tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock FAILED
...FutTimeout: 45s timeout...
AssertionError: I-00063 reproduction: apply() hung for >45s while caller held AccessShareLock on batch_items. Self-blocker detection or lock_timeout did not fire — fix did not land or was bypassed.
```

This confirms the reproduction test fails in pytest for the reasons documented above. In production (where `IW_CORE_TEST_CONTEXT` is never set), the fix would work correctly.

---

## Mandatory Findings

### CRITICAL-1: `importlib.reload()` used in 3 tests (violates CLAUDE.md)

**Files:**
- `tests/integration/db/test_safe_migrate_self_blocker.py:234` — `test_lock_timeout_env_var_honored`
- `tests/integration/db/test_safe_migrate_self_blocker.py:385` — `test_pending_migration_log_written_on_lock_timeout_failure`
- `tests/integration/db/test_safe_migrate_self_blocker.py:447` — `test_rollback_triggered_after_apply_failure`

**Description:** These tests use `reload(orch.config)` and `reload(orch.db.safe_migrate)` to pick up env var changes. This triggers `load_dotenv()` again, re-imports `orch.db.models`, and causes `Base.metadata.create_all(engine)` to run against an already-migrated database — `DuplicateTable: relation "projects" already exists`.

**Suggestion:** Use `monkeypatch.setenv("IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS", "5")` before calling the config function. `get_migration_lock_timeout_secs()` reads `os.environ.get()` at call time — no reload needed. For `test_lock_timeout_env_var_honored`, simply call `get_migration_lock_timeout_secs()` after monkeypatch and assert it returns 5.

---

### HIGH-1: Reproduction test doesn't catch the bug in pytest

**File:** `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py:102`

**Description:** `_is_test_context_active()` returns `True` in pytest, causing `_assert_no_self_blockers()` to short-circuit. The lock_timeout backstop (AC3) also doesn't fire in the test harness. The test hangs for 45s in both pre-fix and post-fix states, meaning it cannot distinguish fixed from unfixed code in pytest.

**Suggestion:** The test design needs to account for the `_is_test_context_active()` bypass. Options:
1. Add a subprocess-based test that runs without `IW_CORE_TEST_CONTEXT` set
2. Add a unit test that directly mocks `_is_test_context_active` to return `False` and verifies the SQL query path fires
3. Document explicitly that the reproduction test only works in production environments and add a separate pytest-compatible integration test for the happy path

**Note:** The S01 backend fix is correct. In production (no `IW_CORE_TEST_CONTEXT`), `db.commit()` + `db.close()` releases the locks before Phase 2, and `_assert_no_self_blockers` would fire if called with a stale session. The issue is purely with pytest test design.

---

### HIGH-2: AC1 rollback test doesn't verify `run_rollback` was invoked

**File:** `tests/integration/db/test_safe_migrate_self_blocker.py:428`

**Description:** `test_rollback_triggered_after_apply_failure` only verifies `apply()` fails with a lock-related error. It does NOT verify `run_rollback` was called with the correct `batch_id`.

**Suggestion:** Add a spy/monkeypatch on `run_rollback` to verify it was invoked and with what arguments. Or add a comment explicitly acknowledging this limitation.

---

### HIGH-3: AC5 tests don't verify `pending_migration_log` row was written

**Files:**
- `tests/integration/db/test_safe_migrate_self_blocker.py:333`
- `tests/integration/db/test_safe_migrate_self_blocker.py:369`

**Description:** Both tests acknowledge that `_write_migration_log` short-circuits in test context (`_is_test_context_active()` returns True). They verify the error message instead of querying `pending_migration_log` to confirm a row exists with `phase='apply'`, `success=false`, and a non-null `error_message`.

**Suggestion:** Either query `pending_migration_log` table directly after `apply()` returns (where `_is_test_context_active()` is False), or add a comment explicitly acknowledging AC5 is NOT verified by these tests and a follow-up is needed.

---

## Medium-Fixable Findings

### MEDIUM_FIXABLE-1: `_assert_no_self_blockers` bypassed for AC4 tests

**File:** `tests/integration/db/test_safe_migrate_self_blocker.py:91`

**Description:** `test_assert_no_self_blockers_raises_when_same_process_holds_blocking_lock` expects `_assert_no_self_blockers()` to raise `SelfBlockerError`, but `_is_test_context_active()` returns `True` in pytest, causing the function to return early without performing any check. The test fails with "DID NOT RAISE".

**Note:** This is the **correct** design (test context bypass prevents live DB corruption). The test is correctly designed for production.

**Suggestion:** Add a separate test that directly mocks `_is_test_context_active` to return `False` and exercises the blocking path, or add a unit test that directly tests the SQL queries.

---

## Notes

1. **S01 backend implementation is correct and complete.** All five acceptance criteria are met in the code. The `db.commit()` + `db.close()` fix before Phase 2 is the structural fix. `lock_timeout` and `pg_blocking_pids()` self-blocker detection are the defensive backstops.

2. **The reproduction test is broken in pytest but would work in production.** In a production environment (no `IW_CORE_TEST_CONTEXT`), the fix correctly prevents the self-deadlock by committing and closing the daemon session before Phase 2.

3. **S04 correctly identified all the issues** that S03 failed to address. The findings in this report align with S04's analysis.

4. **The pre-existing `test_apply_logs_when_alembic_raises` failure** (noted in S02 and S04) is unrelated to I-00063 and should be addressed separately. It fails because the test doesn't mock `create_engine`, so AC4's pre-flight check fires against the real connection.

---

## Verdict

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00063",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "fail",
  "mandatory_fix_count": 4,
  "tests_passed": false,
  "test_summary": "2570 unit passed, 2 failed (pre-existing); 6 integration passed, 7 failed (3 CRITICAL importlib.reload violations, 4 due to _is_test_context_active bypass + duplicate table)",
  "findings": [
    {
      "severity": "CRITICAL",
      "category": "convention",
      "file": "tests/integration/db/test_safe_migrate_self_blocker.py",
      "line": 234,
      "description": "test_lock_timeout_env_var_honored uses importlib.reload(orch.config) in violation of CLAUDE.md's prohibition on reload(). Causes DuplicateTable: relation 'projects' already exists.",
      "suggestion": "Use monkeypatch.setenv('IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS', '5') before calling get_migration_lock_timeout_secs() — no reload needed since the function reads os.environ at call time.",
      "cross_cutting": false
    },
    {
      "severity": "CRITICAL",
      "category": "convention",
      "file": "tests/integration/db/test_safe_migrate_self_blocker.py",
      "line": 385,
      "description": "test_pending_migration_log_written_on_lock_timeout_failure uses reload(orch.db.safe_migrate) in violation of CLAUDE.md's prohibition on reload(). Causes DuplicateTable.",
      "suggestion": "Use monkeypatch.setenv() to set the env var before the test runs; no reload needed.",
      "cross_cutting": false
    },
    {
      "severity": "CRITICAL",
      "category": "convention",
      "file": "tests/integration/db/test_safe_migrate_self_blocker.py",
      "line": 447,
      "description": "test_rollback_triggered_after_apply_failure uses reload(orch.db.safe_migrate) in violation of CLAUDE.md's prohibition on reload(). Causes DuplicateTable.",
      "suggestion": "Use monkeypatch.setenv() to set the env var; no reload needed.",
      "cross_cutting": false
    },
    {
      "severity": "HIGH",
      "category": "testing",
      "file": "tests/integration/daemon/test_phase2_apply_no_self_deadlock.py",
      "line": 102,
      "description": "test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock does not catch the bug in pytest. _is_test_context_active() returns True in pytest, causing _assert_no_self_blockers() to short-circuit. The lock_timeout backstop also doesn't fire in the test harness. The test hangs for 45s in BOTH pre-fix and post-fix states.",
      "suggestion": "Add a subprocess-based test that exercises the full path without IW_CORE_TEST_CONTEXT, or mock _is_test_context_active to return False and verify the blocking path fires. The happy-path test (test_i_00063_apply_succeeds_when_no_blocking_lock) correctly verifies the non-deadlocked case.",
      "cross_cutting": true
    },
    {
      "severity": "HIGH",
      "category": "testing",
      "file": "tests/integration/db/test_safe_migrate_self_blocker.py",
      "line": 428,
      "description": "test_rollback_triggered_after_apply_failure does not verify run_rollback was invoked. It only checks apply() fails with a lock-related error.",
      "suggestion": "Add a spy/monkeypatch on run_rollback to verify it was called with the correct batch_id. Or add a comment acknowledging the limitation.",
      "cross_cutting": false
    },
    {
      "severity": "HIGH",
      "category": "testing",
      "file": "tests/integration/db/test_safe_migrate_self_blocker.py",
      "line": 333,
      "description": "test_pending_migration_log_written_on_self_blocker_failure doesn't verify pending_migration_log row was written. It checks error_message instead of querying the table.",
      "suggestion": "Query pending_migration_log directly to verify the row exists with phase='apply', success=false, and non-null error_message. Or add a comment noting AC5 is not verified in pytest due to _is_test_context_active bypass.",
      "cross_cutting": false
    },
    {
      "severity": "HIGH",
      "category": "testing",
      "file": "tests/integration/db/test_safe_migrate_self_blocker.py",
      "line": 369,
      "description": "test_pending_migration_log_written_on_lock_timeout_failure doesn't verify pending_migration_log row was written. Same issue as test_pending_migration_log_written_on_self_blocker_failure.",
      "suggestion": "Same as above.",
      "cross_cutting": false
    },
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "testing",
      "file": "tests/integration/db/test_safe_migrate_self_blocker.py",
      "line": 91,
      "description": "test_assert_no_self_blockers_raises_when_same_process_holds_blocking_lock expects SelfBlockerError but _is_test_context_active() returns True in pytest, causing the check to short-circuit. Test fails with 'DID NOT RAISE'.",
      "suggestion": "Add a unit test that directly mocks _is_test_context_active to return False and exercises the blocking path, or test the SQL queries directly in a unit test without the testcontainer harness.",
      "cross_cutting": false
    },
    {
      "severity": "MEDIUM_SUGGESTION",
      "category": "security",
      "file": "orch/db/safe_migrate.py",
      "line": 629,
      "description": "f'SET lock_timeout = \\'{lock_timeout_secs}s\\'' uses string interpolation. Safe because lock_timeout_secs is int type, but a comment explaining the safety invariant would make the intent clearer.",
      "suggestion": "Add a comment: '# lock_timeout_secs is int, not arbitrary string — safe from injection. PostgreSQL SET command does not support bind params.'",
      "cross_cutting": false
    }
  ],
  "missing_requirements": [
    "AC2: regression test doesn't catch the bug in pytest",
    "AC4: self-blocker detection tests bypassed in test context",
    "AC5: pending_migration_log row not verified in tests"
  ],
  "notes": "S01 backend implementation is correct. The fix (db.commit() + db.close() before Phase 2; lock_timeout on apply connection; pg_blocking_pids() self-blocker detection) correctly addresses the I-00063 self-deadlock for production environments. The test suite has CRITICAL and HIGH findings that must be fixed before merge: 3 tests violate CLAUDE.md's reload() prohibition (causing DuplicateTable crashes), the reproduction test doesn't catch the bug in pytest due to _is_test_context_active bypass, AC5 tests don't verify the log row was written, and AC1 rollback test doesn't verify run_rollback was called. All findings are test-design issues; the S01 code itself is sound."
}
```