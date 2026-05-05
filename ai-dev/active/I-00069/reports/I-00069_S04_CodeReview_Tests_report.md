# I-00069 S04 Code Review Report — Tests (S03)

**Step**: S04 — Code Review of S03 (tests-impl)
**Agent**: CodeReview
**Work Item**: I-00069 — Downgrade LiveDbConnectionRefusedError to DEBUG/WARNING in test context
**Date**: 2026-05-05

---

## What Was Reviewed

- `tests/dashboard/test_live_db_guard_log_level.py` — 2 tests added in S03
- `dashboard/app.py` — the file under test (confirmed post-S01 state)

---

## Pre-Review Gate Results

| Check | Result |
|-------|--------|
| `make lint` | ✅ PASS — no violations |
| `make format-check` | ✅ PASS — all files formatted |
| `pytest tests/dashboard/test_live_db_guard_log_level.py` | ✅ 2 passed, 0 failed |
| `make test-unit` | ✅ 2581 passed, 4 skipped, 5 xfailed, 1 xpassed |

---

## Checklist Analysis

### 1. Falsifiability

**Test A** (`test_i00069_live_db_guard_refusal_is_not_error_in_test_context`):

Walked through mentally against pre-S01 `dashboard/app.py`:

```python
# Pre-S01 (buggy) path:
try:
    app.state.alembic_guard_status = check_db_at_head()
except Exception:
    logger.exception("alembic guard check failed at startup; continuing")
    app.state.alembic_guard_status = None
```

- `LiveDbConnectionRefusedError` is raised → caught by `except Exception`
- `logger.exception(...)` emits at `ERROR` with `exc_text` containing the class name
- Test A's assertion `error_records_mentioning_refusal == []` would evaluate `False` on that record → **test FAILS on pre-S01** ✅
- On post-S01: `LiveDbConnectionRefusedError` is caught separately and logged at DEBUG → **test PASSES on post-S01** ✅

**Test B** (`test_i00069_non_refusal_exception_still_logs_error`):

- Patches `check_db_at_head` to raise `RuntimeError("synthetic boot failure")`
- The generic `except Exception` path is unchanged post-S01 → logs at ERROR with traceback
- Would PASS on both pre-S01 and post-S01 ✅ (correct — regression test, not a red/green test)

### 2. Semantic Correctness

| Assertion | Assessment |
|-----------|------------|
| `error_records_mentioning_refusal == []` (line 67) | ✅ Negative assertion: no ERROR record with `LiveDbConnectionRefused` substring |
| `debug_records_mentioning_refusal` (line 49–57) | ✅ Semantic assertion: DEBUG record with `LiveDbConnectionRefused` present |
| `app.state.alembic_guard_status is None` (line 45) | ✅ Confirms expected refusal path taken |
| ERROR record with `exc_text` for RuntimeError (lines 95–104) | ✅ Confirms regression path still fires |

No shape-only assertions (e.g., `len > 0` alone). No bare `"guard" in caplog.text"` checks.

### 3. Logger Scope

`caplog.set_level(logging.DEBUG, logger="dashboard.app")` — matches `dashboard/app.py:66`:
```python
logger = logging.getLogger(__name__)  # __name__ == "dashboard.app"
```
✅ DEBUG capture is correctly scoped.

### 4. Isolation and Side Effects

- `monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")` — ✅ uses monkeypatch (auto-reverts)
- `patch("dashboard.app.check_db_at_head", ...)` — ✅ uses patch (context manager)
- No global logger reconfiguration
- No live-DB connection attempts (relies on `_arm_live_db_guard` session fixture)

### 5. Project Conventions

- File location: `tests/dashboard/` — ✅ correct (FastAPI factory + dashboard wiring test)
- Modern type hints: `pytest.LogCaptureFixture`, `pytest.MonkeyPatch`, `-> None` — ✅
- `from __future__ import annotations` — ✅

### 6. Forbidden Patterns

- No `importlib.reload(orch.config)` — ✅ absent
- Not an integration test — N/A
- No live DB connections — `_arm_live_db_guard` fixture prevents it — ✅

---

## Findings

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00069",
  "step_reviewed": "S03",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [],
  "tests_passed": true,
  "test_summary": "2 passed, 0 failed (file scope); 2581 passed, 4 skipped, 5 xfailed, 1 xpassed (full unit)",
  "notes": "Tests correctly fail on pre-S01 code (falsifiability), assert specific log levels (semantic correctness), use correct logger scope, proper monkeypatch/patch isolation, and follow all project conventions. No forbidden patterns. Minor observation: S03 also modified dashboard/app.py to include type(exc).__name__ in DEBUG/WARNING messages (confirmed in S03 report) — this is correct and necessary for the semantic assertion to pass."
}
```

---

## Summary

The S03 test implementation is **correct and complete**. Both tests:

1. **Fail on pre-S01** (red) — the bug produces ERROR-level `LiveDbConnectionRefusedError` records
2. **Pass on post-S01** (green) — the fix demotes the log to DEBUG with no traceback
3. **Regression test** (`test_i00069_non_refusal_exception_still_logs_error`) correctly verifies that non-refusal exceptions still surface at ERROR with traceback, preventing over-correction

No issues found. Proceed to S05.