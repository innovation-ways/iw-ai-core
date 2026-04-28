# S09 QvGate Report — unit-tests

## Gate Result: PASS

**Command:** `make test-unit`
**Exit Code:** 0

## Summary

Ran full unit test suite. All 1910 tests passed (2 skipped), completed in 21.15s.

## Test Results

| Metric | Value |
|--------|-------|
| Passed | 1910 |
| Skipped | 2 |
| Warnings | 48 (deprecation/unknown config) |
| Duration | 21.15s |

## Files Changed

No files were modified by this step — it was a quality gate execution only.

## Observations

- Minor deprecation warnings in `test_safe_migrate.py` and `test_safe_migrate_guards.py` related to `_assert_not_agent_context` (now superseded by `orch.db.live_db_guard.assert_engine_url_allowed`)
- Several `datetime.utcnow()` deprecation warnings in QA engine tests
- Some async warning in `test_qa_engine.py` tests (coroutine never awaited) — RuntimeWarning, not an error
- One `PytestCollectionWarning` for `TestRunStatus` enum being incorrectly treated as a test class