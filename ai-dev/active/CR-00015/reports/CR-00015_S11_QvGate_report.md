# CR-00015 S11 QV Gate Report

## Gate: unit-tests
**Command**: `make test-unit`
**Result**: PASS (exit code 0)

## Summary

Ran the full unit test suite via `make test-unit`. All 1182 tests passed in 8.70s.

## Test Results

- **Total**: 1182 passed
- **Warnings**: 18 (deprecation warnings for datetime.utcnow(), coroutine not awaited, etc. — none critical)
- **Duration**: 8.70s

## Observations

- No test failures or errors
- Some async mock warnings in `test_qa_engine.py` and `test_f00055_boundaries.py` — coroutines not awaited but tests still pass (likely pre-existing)
- `TestRunStatus` pytest collection warning — an enum named `TestRunStatus` is being picked up by pytest as a test class, but it doesn't affect functionality

No files were modified in this step — this was a read-only quality gate execution.