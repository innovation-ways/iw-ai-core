# F-00066 S11 QV Gate Report

## Gate: unit-tests
**Command**: `make test-unit`
**Result**: PASS

## Summary

Executed the unit test suite via `make test-unit`. All 1982 tests passed (2 skipped) with 48 warnings.

## Test Results

- **Total**: 1982 passed, 2 skipped
- **Duration**: 32.28s
- **Exit code**: 0

## Warnings

The test run produced 48 warnings, all non-fatal:
- Deprecation warnings for `datetime.utcnow()` (in QA engine tests)
- Deprecation warnings for `_assert_not_agent_context` (in safe_migrate tests)
- `PytestCollectionWarning` for `TestRunStatus` enum having `__init__`
- `RuntimeWarning` for unawaited coroutines in `test_answer_stream*` tests (async mock issues)
- `timeout` argument warning with Starlette `TestClient`
- `DeprecationWarning` for `datetime.utcnow()` scattered across QA engine tests

## Issues/Observations

No test failures. The warnings are pre-existing and unrelated to any changes in this work item.