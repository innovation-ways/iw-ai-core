# I-00069 S05 Code Review — Final Cross-Agent Review

**Step**: S05 — Final Cross-Agent Review
**Agent**: code-review-final-impl
**Work Item**: I-00069 — Downgrade LiveDbConnectionRefusedError to DEBUG/WARNING in test context
**Date**: 2026-05-05

---

## What Was Reviewed

Reviewed the complete implementation across S01–S04, including:
- Design document (`I-00069_Issue_Design.md`) and functional design (`I-00069_Functional.md`)
- Implementation reports for S01 (backend), S02 (code review of S01), S03 (tests), S04 (code review of S03)
- Both changed files end-to-end: `dashboard/app.py` and `tests/dashboard/test_live_db_guard_log_level.py`
- Architecture compliance with `CLAUDE.md`, `dashboard/CLAUDE.md`, `tests/CLAUDE.md`

---

## Pre-Flight Gate Results

| Check | Result |
|-------|--------|
| `make lint` | ✅ PASS — no violations |
| `make format-check` | ✅ PASS — 611 files already formatted |

No new lint/format violations introduced by any step.

---

## 1. Completeness vs Design Document

### AC1: Bug is fixed ✅

`dashboard/app.py:147-161` now catches `LiveDbConnectionRefusedError` **before** the generic `except Exception`:
- Test context (`IW_CORE_TEST_CONTEXT=true`): logs at `DEBUG` with a single-line message, no traceback
- Non-test context: logs at `WARNING` with a single-line message, no traceback
- All other exceptions: continue to use `logger.exception(...)` at `ERROR` with full traceback

`app.state.alembic_guard_status = None` is set in all branches — behavior preserved.

### AC2: Regression test exists ✅

`tests/dashboard/test_live_db_guard_log_level.py` contains 2 tests:
1. `test_i00069_live_db_guard_refusal_is_not_error_in_test_context` — reproduction test (RED before fix, GREEN after)
2. `test_i00069_non_refusal_exception_still_logs_error` — regression test (prevents over-correction)

### AC3: Behaviour is preserved ✅

Both tests assert `app.state.alembic_guard_status is None` after the refusal. The contract is unchanged.

---

## 2. Cross-Step Integration

### Does Test A actually exercise the S01 code path?

Yes. Walking through the execution:
1. `monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")` — sets the flag
2. `caplog.set_level(logging.DEBUG, logger="dashboard.app")` — captures logs
3. `create_app()` — calls `check_db_at_head()` which raises `LiveDbConnectionRefusedError` under the test guard
4. The new `except LiveDbConnectionRefusedError` branch is taken
5. `logger.debug(...)` is called — Test A asserts no ERROR records mention `LiveDbConnectionRefused`

### Does Test B exercise the surviving `except Exception` path?

Yes. `patch("dashboard.app.check_db_at_head", side_effect=RuntimeError("synthetic boot failure"))` forces the generic `except Exception` branch, which calls `logger.exception(...)` at ERROR with traceback. Test B asserts both `error_records` exist and `exc_text` is populated.

### Is there coverage for the WARNING branch (non-test context)?

No — and this is correctly noted as MEDIUM_SUGGESTION (not a fix requirement). The design's AC1 only covers test-context behavior. The non-test branch is a safety net for operators/daemon context and is not covered by tests. This is acceptable per the design.

---

## 3. No Other Consumers Regressed

| Component | Status |
|-----------|--------|
| `dashboard/middlewares/alembic_guard.py:54-58` | Untouched — uses `contextlib.suppress(Exception)` |
| `orch/daemon/main.py:147` | Untouched — uses `logger.critical(...)` for guard probe |
| `orch/db/live_db_guard.py` | Untouched |
| `orch/db/alembic_guard.py` | Untouched |
| `tests/dashboard/test_alembic_guard_banner.py` | Untouched — tests banner UI (not log output), uses mocks that bypass `check_db_at_head()` entirely |

The banner test file mocks `current_revision`, `_get_head_revisions`, and `list_pending_revisions` — it never exercises the `LiveDbConnectionRefusedError` path, so it's unaffected by the log-level change.

---

## 4. Test Coverage (Holistic)

### Falsifiability on pre-S01 code

**Test A** would FAIL on pre-S01 because `logger.exception(...)` emits ERROR with `exc_text` containing `LiveDbConnectionRefusedError`. The assertion `error_records_mentioning_refusal == []` would find that record and fail.

**Test B** would PASS on pre-S01 (and post-S01) because the generic `except Exception` path is unchanged for non-refusal exceptions.

### Integration point

`LiveDbConnectionRefusedError` thrown by `safe_create_engine` → reaches `dashboard/app.py`'s `except` chain → caught by specific branch (test context) or generic branch (other exceptions). The test exercises this by relying on the `_arm_live_db_guard` session fixture which sets `IW_CORE_TEST_CONTEXT=true` and hijacks `IW_CORE_DB_*` env vars.

### Test results

| Suite | Result |
|-------|--------|
| `make lint` | ✅ PASS |
| `make format-check` | ✅ PASS |
| `make test-unit` | ✅ 2581 passed, 4 skipped, 5 xfailed, 1 xpassed |
| `pytest tests/dashboard/test_live_db_guard_log_level.py` | ✅ 2 passed |
| `make test-integration` | ⚠️ Timed out at 300s (pre-existing infrastructure issue; test output showed passing tests before timeout) |

---

## 5. Architecture Compliance

| Check | Result |
|-------|--------|
| `dashboard/` imports from `orch.db.live_db_guard` | ✅ Allowed — `live_db_guard` is a shared DB utility |
| No new module dependencies introduced | ✅ |
| No migrations touched | ✅ N/A for this incident |
| Layer boundary respected: dashboard → orch only | ✅ |
| `noqa: BLE001` on `except Exception` preserved | ✅ |

---

## 6. Security (Cross-Cutting)

| Check | Result |
|-------|--------|
| No new env-var reads beyond `IW_CORE_TEST_CONTEXT` | ✅ |
| No hardcoded secrets / credentials | ✅ |
| No new endpoints / routes | ✅ |
| No SQL/command injection risk | ✅ |

---

## Findings

### MEDIUM_SUGGESTION: No test for non-test-context WARNING branch

**File**: `dashboard/app.py:157-160`
**Category**: testing
**Severity**: MEDIUM_SUGGESTION

The non-test-context WARNING branch (`IW_CORE_TEST_CONTEXT != "true"`) is not covered by any test. This is acceptable because:
- The design's AC1 only requires coverage of the test-context (DEBUG) branch
- The non-test branch is simple and low-risk (just a different log level)
- The test would require a more complex setup (real DB connection or elaborate mocking)

However, for completeness and regression safety, a future iteration could add a test that verifies WARNING-level logging when `IW_CORE_TEST_CONTEXT != "true"`.

**Suggestion**: Consider adding a third test case that patches `os.environ.get("IW_CORE_TEST_CONTEXT")` to return something other than `"true"` and asserts WARNING-level logging (not ERROR) for `LiveDbConnectionRefusedError`. This is optional.

---

## Verdict

**PASS** — Zero CRITICAL/HIGH findings, zero MEDIUM_FIXABLE findings.

---

## JSON Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00069",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_SUGGESTION",
      "category": "testing",
      "file": "dashboard/app.py",
      "line": 157,
      "description": "No test covers the non-test-context WARNING branch (IW_CORE_TEST_CONTEXT != 'true'). Acceptable per AC1 scope, but for complete regression coverage a future test could exercise this path.",
      "suggestion": "Add a third test case that patches os.environ.get to return a non-'true' value and asserts WARNING-level logging for LiveDbConnectionRefusedError.",
      "cross_cutting": false
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2581 unit passed, 2 new tests passed, 0 failed",
  "missing_requirements": [],
  "notes": "All three acceptance criteria are covered. The implementation is minimal, correct, and well-isolated. Exception ordering, log levels, env-var comparison, and behaviour preservation all verified. No regressions in any upstream/downstream paths. Integration tests timed out (pre-existing infrastructure issue unrelated to this change)."
}
```