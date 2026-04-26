# QV Gate Report — S09: unit-tests

**Gate**: unit-tests  
**Command**: `make test-unit`  
**Result**: PASS

## Summary

Ran the full unit test suite via `make test-unit`. All 1547 tests passed.

## Output

- **Tests**: 1547 passed
- **Warnings**: 27 (deprecation warnings for `datetime.utcnow()`, coroutine warnings in a few async test mocks, pytest config warning for unknown `env` option)
- **Duration**: 12.87s
- **Exit code**: 0

## Issues / Observations

- No failures. The warnings are pre-existing (deprecation, coroutine mock patterns, pytest config) and do not affect correctness.
- No files changed as part of this gate — it is read-only verification.