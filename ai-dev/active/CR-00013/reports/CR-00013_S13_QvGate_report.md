# CR-00013 S13 — QV Gate Report

## Gate: unit-tests

**Command:** `make test-unit`
**Result:** PASS

## Summary

Ran the full unit test suite via `make test-unit`. All 1295 tests passed in ~15 seconds.

## Test Results

- **Total:** 1295 passed
- **Warnings:** 19 (deprecation warnings from test mocks and `utcnow()`, not errors)
- **Duration:** 14.79s

No failures or errors.

## Observations

- Some `RuntimeWarning: coroutine '...' was never awaited` warnings appear in async tests — these are pre-existing and do not affect test correctness.
- One `PytestCollectionWarning` for `TestRunStatus` (name collision with an enum) — pre-existing.
- No new regressions introduced.
