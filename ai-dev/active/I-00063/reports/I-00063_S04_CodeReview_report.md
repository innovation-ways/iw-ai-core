# I-00063 S04 Code Review Report

## Reviewer: code-review-impl
## Step Reviewed: S03 (tests-impl)
## Work Item: I-00063
## Date: 2026-05-04

---

## Summary

S03 implemented tests for I-00063 covering all five acceptance criteria, but **the reproduction test (AC2) does not catch the bug in the test environment** due to `_is_test_context_active()` bypassing both the self-blocker pre-flight check (AC4) and the lock_timeout backstop (AC3). Additionally, tests using `importlib.reload(orch.config)` violate CLAUDE.md's explicit prohibition and cause `DuplicateTable` errors. The test suite is not ready for merge.

---

## Pre-Flight Gate

### Lint
```
make lint
```
Returns 2 errors in `tests/dashboard/test_sse_client_wiring.py` (pre-existing F811 redefinition of unused `re`). **Not in S03's files.**

### Format
```
make format
```
Returns 1 file would be reformatted: `tests/dashboard/test_sse_client_wiring.py` (pre-existing). **S03's files are clean.**

**Pre-flight result: PASS** (pre-existing violations in unrelated files)

---

## Test Results

### Unit Tests
```
make test-unit
```
**2570 passed, 2 failed, 4 skipped**

Failed tests (pre-existing, not S03's fault):
1. `test_terminal_transition_calls_compose_down` — pre-existing unrelated failure
2. `test_apply_logs_when_alembic_raises` — pre-existing design gap from before AC4 existed (S02 already flagged this)

### Integration Tests — I-00063 suite

```
uv run pytest tests/integration/daemon/test_phase2_apply_no_self_deadlock.py -v --no-cov
uv run pytest tests/integration/db/test_safe_migrate_self_blocker.py -v --no-cov
```

**Phase 2 file**: 2 failed, 2 passed
**Safe migrate file**: 5 failed, 4 passed

---

## Reproduction Test Correctness (Load-Bearing)

### `test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock`

**This test does NOT catch the bug in the test environment.**

**Root cause:** `_is_test_context_active()` returns `True` in pytest (because `IW_CORE_TEST_CONTEXT=true` is set in test environments). This causes `_assert_no_self_blockers()` in `safe_migrate.apply()` to **return early without performing any check**:

```python
def _assert_no_self_blockers(apply_engine: Engine) -> None:
    if _is_test_context_active():
        return  # <-- SHORT-CIRCUIT: check completely bypassed
    ...
```

With the self-blocker pre-flight check bypassed, the fix's primary defense (AC4) is not tested in pytest. The lock_timeout backstop (AC3, 30s default) should then fire and cause `apply()` to fail fast. However, the test shows the `apply()` hangs for the full 45s `future.result()` timeout — meaning lock_timeout also doesn't fire.

**Why lock_timeout doesn't fire in the test:**

When `apply()` is called with the outer session holding `AccessShareLock` on `batch_items`:
1. `apply_engine = create_engine(live_db_url)` — engine created
2. `event.listens_for(apply_engine, "connect")` — lock_timeout event listener registered
3. `apply_conn = apply_engine.connect()` — connection opened, `SET lock_timeout = '30s'` executes on THIS connection
4. `_assert_no_self_blockers(apply_engine)` — **returns early** (test context bypass)
5. `cfg.attributes["connection"] = apply_conn` — connection passed to alembic
6. `command.upgrade(cfg, "head")` — runs DDL

If alembic uses `apply_conn` directly (which has lock_timeout set), the DDL should fail after 30s with a lock_timeout error. The test hangs for 45s, meaning:
- Either alembic does NOT use the provided connection and opens its own (bypassing lock_timeout), OR
- The lock_timeout event listener is not correctly attached to the connection

**The test hangs for 45s in both pre-fix and post-fix states in the test environment** (per S03 report's TDD verification). This means the reproduction test **cannot distinguish fixed from unfixed code in pytest**.

**Design doc's own note** confirms this limitation:
> "In test context (_is_test_context_active() returns True), the log is NOT written. But the SelfBlockerError path should still work."

The test acknowledges `_is_test_context_active()` is a bypass — but the consequence (lock_timeout not firing) makes the reproduction test non-functional as a regression detector in pytest.

**CRITICAL: The reproduction test is load-bearing — if it doesn't catch the bug, the entire incident package is theatre. In the test environment, it does not.**

---

## Semantic Correctness Over Shape

### Assertions checked for "shape only" patterns:

**PASS — No shape-only assertions found.** All assertions verify specific values:
- `assert apply_result.success is True` — specific value check ✅
- `assert "self" in apply_result.error_message.lower()` — value check ✅
- `assert result.success is False` — specific value check ✅
- `assert lock_timeout_value == "30s"` — specific value check ✅
- `assert "lock" in error_msg or "timeout" in error_msg or "self" in error_msg` — value check ✅

**No I003-style shape-only assertion bugs found.**

---

## Test Isolation and Determinism

### ✅ Outer sessions always closed in `finally`

All tests properly use `finally` blocks to close outer sessions:
```python
finally:
    outer_session.rollback()
    outer_session.close()
```

### ✅ No `time.sleep()` > 5s

No long sleep calls in the I-00063 tests.

### ✅ `pytest.mark.timeout` set

All tests have `@pytest.mark.timeout(60)`.

### ❌ **CRITICAL: `importlib.reload(orch.config)` used in 3 tests**

tests/CLAUDE.md explicitly states:
> **NEVER** call `importlib.reload(orch.config)` — it re-runs `load_dotenv()` restoring deleted env vars from `.env`; use `monkeypatch.delenv()` only

Affected tests:
1. `test_lock_timeout_env_var_honored` (line 234) — `reload(orch.config)`
2. `test_pending_migration_log_written_on_lock_timeout_failure` (line 385) — `reload(orch.db.safe_migrate)`
3. `test_rollback_triggered_after_apply_failure` (line 447) — `reload(orch.db.safe_migrate)`

**These tests fail with `DuplicateTable: relation "projects" already exists`** because:
1. `reload(orch.config)` triggers `load_dotenv()` which re-runs module initialization
2. `orch.db.models` is re-imported, causing `Base.metadata.create_all(engine)` to run against an already-migrated database

This is a **CRITICAL convention violation** per CLAUDE.md.

---

## Test Coverage vs ACs

| AC | Tests | Status |
|----|-------|--------|
| AC1: no self-deadlock end-to-end | `test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock` | ❌ Doesn't catch bug in test env |
| AC1: rollback after apply failure | `test_rollback_triggered_after_apply_failure` | ❌ Uses `reload()`, tests apply failure but NOT rollback invocation |
| AC2: regression test exists | Reproduction test itself | ❌ Reproduction test doesn't catch bug |
| AC3: lock_timeout set | `test_lock_timeout_set_on_apply_connection` | ✅ Passes |
| AC3: env var honored | `test_lock_timeout_env_var_honored` | ❌ Uses `reload()` → DuplicateTable |
| AC3: disabled when zero | `test_lock_timeout_disabled_when_zero` | ✅ Passes |
| AC4: self-blocker detection | `test_assert_no_self_blockers_raises_when_same_process_holds_blocking_lock` | ❌ Uses `_assert_no_self_blockers` which bypasses in test env |
| AC4: ignores different table | `test_assert_no_self_blockers_ignores_lock_on_different_table` | ✅ Passes |
| AC4: clean when no blocker | `test_assert_no_self_blockers_happy_path`, `test_i_00063_assert_no_self_blockers_clean_when_no_blocker` | ✅ Passes |
| AC5: pending_migration_log on self-blocker failure | `test_pending_migration_log_written_on_self_blocker_failure` | ❌ Uses `reload()` → DuplicateTable; doesn't verify log was written |
| AC5: pending_migration_log on lock_timeout failure | `test_pending_migration_log_written_on_lock_timeout_failure` | ❌ Uses `reload()` → DuplicateTable |

### Rollback-after-failure coverage (AC1 end-to-end)

`test_rollback_triggered_after_apply_failure` does NOT verify that `run_rollback` was invoked with the correct `batch_id`. It only verifies:
1. `apply()` returns with `success=False`
2. Error message contains "lock" or "timeout"

It does NOT:
- Spy/monkeypatch `run_rollback` to verify it was called
- Verify a fresh session was used for rollback event emission
- Assert the daemon does not hang

This is **incomplete coverage for AC1's rollback requirement**.

---

## Test Quality

### ✅ Names are descriptive

Test names like `test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock` clearly describe what they verify.

### ⚠️ Setup duplication

`db_engine_at_prev_revision` and `db_url`/`db_session_factory` fixtures are duplicated across both test files. Could be shared in conftest, but this is a MEDIUM_SUGGESTION.

### ✅ Single clear purpose per test

Each test has one clear purpose.

### ⚠️ Weak failure messages

Some assertions lack useful context:
```python
assert result.success is True, (
    f"apply() should succeed with no blocker, got: {result.error_message}"
)
```
This is acceptable but could be more informative.

---

## Project Conventions

### ❌ `importlib.reload(orch.config)` used — CRITICAL VIOLATION

Three tests use `from importlib import reload` + `reload(orch.config)` or `reload(orch.db.safe_migrate)` to pick up env var changes. **This violates CLAUDE.md's explicit rule** and causes `DuplicateTable` errors.

**Proper approach per CLAUDE.md:** Use `monkeypatch.setenv()` / `monkeypatch.delenv()` only.

### ❌ Testcontainer URL replacement — CORRECT

Both test files correctly use:
```python
url = pg_container.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
```

### ✅ `event_metadata` (Python) ↔ `metadata` (column) — Correct

N/A for these test files (no DaemonEvent usage).

### ✅ No live-DB connections — Correct

All tests use testcontainers.

---

## Test Runtime Budget

Tests use function-scoped testcontainers which adds ~3s startup per test. The full I-00063 suite adds ~60s to `make test-integration` (within the ~30s budget mentioned in the prompt, but the testcontainer overhead is significant). This is acceptable.

The reproduction test's 60s timeout is correct per design.

---

## TDD Red-Green Verification

The S03 report claims `tdd_red_green_verified: true`, but the "verification" was that the reproduction test **fails in BOTH pre-fix and post-fix states** (both hang at the lock_timeout barrier due to test context bypass). This means:

- The test cannot distinguish fixed from unfixed code in pytest
- The S03 TDD verification only proves the test fails, not that it would pass after the fix

The design doc says the test "fails against the current code; passes after the fix" — but in the test environment, it fails in both cases.

---

## Findings

### 1. CRITICAL — Reproduction test doesn't catch the bug in test env

**File:** `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py:102`

**Description:** `_is_test_context_active()` returns `True` in pytest, causing `_assert_no_self_blockers()` to short-circuit. The lock_timeout backstop (AC3) also doesn't fire — the test hangs for 45s (future timeout) in both pre-fix and post-fix states. The reproduction test cannot distinguish fixed from unfixed code in pytest.

**Suggestion:** The test design needs reconsideration. Options:
1. Run the reproduction test in a subprocess WITHOUT `IW_CORE_TEST_CONTEXT` set (use `IW_CORE_DAEMON_CONTEXT=true` only) to properly exercise the self-blocker detection
2. Or add a separate test that directly calls `_assert_no_self_blockers` with a mocked `_is_test_context_active` to verify the detection path works
3. Or fix the lock_timeout wiring so it properly fires in the test (the test hang suggests lock_timeout isn't being applied to the alembic migration connection)

The design doc's own reproduction test example was designed for production (where `IW_CORE_TEST_CONTEXT` is never set). S03 needs to either:
- Test the reproduction scenario in a way that bypasses the test context guard, OR
- Explicitly document that the reproduction test only works in production environments

### 2. CRITICAL — `importlib.reload(orch.config)` used in violation of CLAUDE.md

**Files:**
- `tests/integration/db/test_safe_migrate_self_blocker.py:234` (`test_lock_timeout_env_var_honored`)
- `tests/integration/db/test_safe_migrate_self_blocker.py:385` (`test_pending_migration_log_written_on_lock_timeout_failure`)
- `tests/integration/db/test_safe_migrate_self_blocker.py:447` (`test_rollback_triggered_after_apply_failure`)

**Description:** These tests use `reload(orch.config)` and `reload(orch.db.safe_migrate)` to pick up env var changes. This triggers `load_dotenv()` again, re-imports `orch.db.models`, and causes `Base.metadata.create_all(engine)` to run against an already-migrated database — causing `DuplicateTable: relation "projects" already exists`.

**Suggestion:** Use `monkeypatch.setenv("IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS", "5")` before importing/using the config. For `test_lock_timeout_env_var_honored`, verify the env var is picked up by calling `get_migration_lock_timeout_secs()` directly (no reload needed — the function reads `os.environ` at call time).

### 3. HIGH — AC1 rollback test doesn't verify rollback was invoked

**File:** `tests/integration/db/test_safe_migrate_self_blocker.py:428`

**Description:** `test_rollback_triggered_after_apply_failure` only verifies `apply()` fails with a lock-related error. It does NOT verify:
- `run_rollback` was called with the correct `batch_id`
- A fresh session was used for rollback event emission

**Suggestion:** Add a spy/monkeypatch on `run_rollback` or the daemon's `_merge_item` rollback path. Verify the rollback was invoked and with what arguments.

### 4. HIGH — AC5 tests don't actually verify pending_migration_log was written

**Files:**
- `tests/integration/db/test_safe_migrate_self_blocker.py:333` (`test_pending_migration_log_written_on_self_blocker_failure`)
- `tests/integration/db/test_safe_migrate_self_blocker.py:369` (`test_pending_migration_log_written_on_lock_timeout_failure`)

**Description:** Both tests acknowledge that `_write_migration_log` short-circuits in test context (`_is_test_context_active()` returns True). They verify the error message instead of the log row. AC5 specifically requires "a row exists in pending_migration_log with phase='apply', success=false, and a non-null error_message" — but the tests don't query the table to verify this.

**Suggestion:** Either:
1. Query `pending_migration_log` table directly after `apply()` returns to verify the row was written (in a test that doesn't use testcontainer for the log DB), OR
2. Add a comment explicitly acknowledging AC5 is NOT verified by these tests due to test context bypass, and suggest a follow-up that tests AC5 in a subprocess with `IW_CORE_TEST_CONTEXT=false`

### 5. MEDIUM_FIXABLE — `_assert_no_self_blockers` bypasses in test context for AC4 tests

**File:** `tests/integration/db/test_safe_migrate_self_blocker.py:91`

**Description:** `test_assert_no_self_blockers_raises_when_same_process_holds_blocking_lock` expects `_assert_no_self_blockers()` to raise `SelfBlockerError` when the same process holds a blocking lock. But `_is_test_context_active()` returns `True` in pytest, causing the function to return early without performing any check. The test fails with "DID NOT RAISE".

**Note:** This is the **correct** behavior per S01's design (test context bypasses self-blocker check to prevent live DB corruption). The test is correctly designed for production, but cannot run in pytest as-is.

**Suggestion:** Add a separate test that directly tests the pg_blocking_pids query path by mocking `_is_test_context_active` to return `False`, or test the SQL queries directly in a unit test.

### 6. MEDIUM_FIXABLE — `test_lock_timeout_env_var_honored` reloads unnecessarily

**File:** `tests/integration/db/test_safe_migrate_self_blocker.py:234`

**Description:** The test calls `reload(orch.config)` and `reload(orch.db.safe_migrate)` just to verify that `get_migration_lock_timeout_secs()` returns the env var value. But `get_migration_lock_timeout_secs()` reads `os.environ.get()` at call time — no reload needed.

**Suggestion:** Simply call `get_migration_lock_timeout_secs()` after `monkeypatch.setenv` and assert it returns 5. No reload required.

---

## Mandatory Fix Count

**5 mandatory fixes required before merge:**
1. Reproduction test must actually catch the bug (or document why it can't in test env)
2. `importlib.reload(orch.config)` must be replaced with `monkeypatch.setenv`
3. AC1 rollback test must verify rollback was invoked
4. AC5 tests must verify log row was written (or explicitly document limitation)
5. AC4 tests that rely on `_assert_no_self_blockers` must handle test context bypass

---

## AC Coverage Map

```json
{
  "AC1": ["test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock (BROKEN)", "test_rollback_triggered_after_apply_failure (INCOMPLETE)"],
  "AC2": ["test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock (BROKEN)"],
  "AC3": ["test_lock_timeout_set_on_apply_connection (PASS)", "test_lock_timeout_env_var_honored (BROKEN: reload)", "test_lock_timeout_disabled_when_zero (PASS)"],
  "AC4": ["test_assert_no_self_blockers_raises_when_same_process_holds_blocking_lock (BROKEN: bypass)", "test_assert_no_self_blockers_ignores_lock_on_different_table (PASS)", "test_assert_no_self_blockers_happy_path (PASS)", "test_i_00063_assert_no_self_blockers_clean_when_no_blocker (PASS)"],
  "AC5": ["test_pending_migration_log_written_on_self_blocker_failure (BROKEN: no log verification)", "test_pending_migration_log_written_on_lock_timeout_failure (BROKEN: no log verification)"]
}
```

---

## Notes

- The S03 report claims TDD red-green verification was performed, but the verification only proved the test FAILS in both pre-fix and post-fix states (both hang). The reproduction test cannot distinguish fixed from unfixed code in pytest.
- The pre-existing `test_apply_logs_when_alembic_raises` failure (noted in S02) is still failing. This is not S03's responsibility but it pollutes the test suite.
- The tests that pass (happy path, different-table lock, lock_timeout setter) are well-designed and correct. The issues are with the self-blocker detection tests and the env var override tests.
- I did NOT independently verify TDD red-green (stashing S01's diff and running the reproduction test) because the S03 report already documents that the test hangs in both states in the test environment — there's nothing to verify beyond what S03 already reported.