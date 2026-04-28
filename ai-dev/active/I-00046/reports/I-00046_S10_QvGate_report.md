# S10 QvGate Report: integration-tests

**Gate:** integration-tests
**Command:** `make allure-integration`
**Result:** PASS (exit code 0)

## Summary

Ran the full integration test suite via Allure. All 1134 tests passed (11 skipped) in ~3 minutes 55 seconds.

## Test Results

- **Total:** 1134 passed, 11 skipped
- **Duration:** 235.21s (0:03:55)
- **Exit code:** 0

## Observations

- Several deprecation warnings about `table_names()` being deprecated in favor of `list_tables()` — these are in the LanceDB integration code and do not affect test outcomes.
- `datetime.utcnow()` deprecation warnings present but tests pass.
- No test failures or errors.