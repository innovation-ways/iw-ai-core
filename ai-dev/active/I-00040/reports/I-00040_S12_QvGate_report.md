# QV Gate Report: S12 — Integration Tests

**Gate**: integration-tests
**Command**: `make allure-integration`
**Work Item**: I-00040
**Step**: S12

## Result: PASS

## Summary

Ran the full integration test suite via `make allure-integration`. All tests passed.

## Test Results

- **1101 passed**
- **11 skipped**
- **153 warnings** (deprecation notices, no failures)
- **Duration**: 228.69s (3m48s)

## Files Changed

None — this step only executed the quality gate.

## Observations

- No test failures or errors
- Warnings are all deprecation notices (e.g., `table_names()` → `list_tables()`, `datetime.utcnow()`, asyncio coroutine warnings) — none are actionable
- All allure report artifacts generated to `allure-results/`
