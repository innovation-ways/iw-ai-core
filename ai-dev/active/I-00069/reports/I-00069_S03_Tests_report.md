# I-00069 S03 Tests Report

**Step**: S03 — Tests Implementation
**Agent**: tests-impl
**Work Item**: I-00069 — Downgrade LiveDbConnectionRefusedError to DEBUG/WARNING in test context
**Date**: 2026-05-05

---

## What Was Done

Created `tests/dashboard/test_live_db_guard_log_level.py` with two tests:

1. **`test_i00069_live_db_guard_refusal_is_not_error_in_test_context`** (reproduction test):
   - Verifies that under `IW_CORE_TEST_CONTEXT=true`, the expected `LiveDbConnectionRefusedError` is logged at DEBUG (not ERROR) with no traceback
   - Contains a semantic assertion: at least one DEBUG-level record mentioning `LiveDbConnectionRefused`
   - Contains a negative assertion: no ERROR-level record mentions `LiveDbConnectionRefused`
   - Verifies `app.state.alembic_guard_status is None` after creation

2. **`test_i00069_non_refusal_exception_still_logs_error`** (regression test):
   - Verifies that a non-refusal exception (`RuntimeError("synthetic boot failure")`) still logs at ERROR with a full traceback
   - Prevents over-correction where the fix accidentally silences genuine boot failures
   - Verifies `app.state.alembic_guard_status is None`

Additionally, updated `dashboard/app.py` to include `type(exc).__name__` in the DEBUG/WARNING messages so the exception class name appears in the log message (enabling the semantic assertion to work).

---

## Files Changed

| File | Change |
|------|--------|
| `tests/dashboard/test_live_db_guard_log_level.py` | NEW — 2 tests |
| `dashboard/app.py` | Minor fix: include `type(exc).__name__` in DEBUG/WARNING messages so class name appears in log output |

---

## S01 Message Update

The S01 implementation was updated to include the exception class name in the log message:

```python
# Before (S01):
logger.debug(
    "alembic guard skipped: live DB connection refused under IW_CORE_TEST_CONTEXT=true"
)

# After (S03 fix):
logger.debug(
    "alembic guard skipped: %s: live DB connection refused under IW_CORE_TEST_CONTEXT=true",
    type(exc).__name__,
)
```

This ensures the semantic assertion (DEBUG record mentions `LiveDbConnectionRefused`) passes, as required by the step instructions.

---

## Preflight Results

| Command | Result |
|---------|--------|
| `make format` | `ok` — all files formatted |
| `make typecheck` | `ok` — no issues |
| `make lint` | `ok` — all checks passed |

---

## Test Results

- **New tests**: `tests/dashboard/test_live_db_guard_log_level.py` — 2 passed, 0 failed
- **Full unit suite**: 2581 passed, 4 skipped, 5 xfailed, 1 xpassed

---

## Notes

- The S01 implementation's DEBUG message originally did not include the exception class name, which caused the semantic assertion (`"LiveDbConnectionRefused" in r.getMessage()`) to fail. This was corrected by including `type(exc).__name__` in the log message format string.
- The `_arm_live_db_guard` session fixture sets `IW_CORE_TEST_CONTEXT=true` at session start and hijacks `IW_CORE_DB_*` env vars to an unreachable address. The tests rely on this fixture.
- The tests use `caplog.set_level(logging.DEBUG, logger="dashboard.app")` to capture DEBUG logs specifically on the `dashboard.app` logger, avoiding interference with other loggers.

---

## TDD Verification

- **Test A (reproduction)**: Would FAIL on `main` (pre-S01) because `logger.exception(...)` is called at ERROR with `LiveDbConnectionRefusedError` in `exc_text`. The test checks for no ERROR record mentioning `LiveDbConnectionRefused`, which would fail.
- **Test B (regression)**: Would PASS on both `main` and post-S01 because the generic `except Exception` path is unchanged for non-refusal exceptions.

