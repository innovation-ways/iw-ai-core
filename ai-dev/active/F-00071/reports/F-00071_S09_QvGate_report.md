# F-00071 S09 QV Gate Report

## Gate
- **Name**: unit-tests
- **Command**: `make test-unit`
- **Result**: PASS

## Summary
Ran the full unit test suite via `make test-unit`. All tests passed.

## Results
- **Passed**: 2077
- **Skipped**: 2
- **Warnings**: 48 (deprecation warnings, no failures)
- **Duration**: 39.69s
- **Exit code**: 0

## Observations
- No test failures or errors
- 48 warnings are deprecation notices (datetime.utcnow(), unknown pytest config, etc.) — all pre-existing, none introduced by this work item
- 2 skipped tests — pre-existing skips, not related to this work item
