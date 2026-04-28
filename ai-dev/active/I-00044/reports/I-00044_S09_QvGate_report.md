# QV Gate Report: Unit Tests (S09)

**Gate:** unit-tests
**Command:** `make test-unit`
**Work Item:** I-00044

## Result: PASS

## Summary

Ran the full unit test suite via `make test-unit`. All 1910 tests passed (2 skipped, 48 warnings).

## Test Results

- **Total:** 1910 passed, 2 skipped, 48 warnings
- **Duration:** 20.94s
- **Exit Code:** 0

## Observations

- Deprecation warnings present for `datetime.utcnow()` (to be migrated to timezone-aware)
- Several `RuntimeWarning` about unawaited coroutines in `test_qa_engine.py` async tests
- Some `_assert_not_agent_context` deprecation warnings (migration in progress)
- No test failures or errors