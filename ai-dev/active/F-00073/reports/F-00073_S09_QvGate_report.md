# F-00073 S09 QV Gate Report

## Gate: unit-tests
**Command**: `make test-unit`
**Result**: PASS

## Summary

Ran unit tests via `make test-unit`. All tests passed.

## Test Results

- **Total**: 2150 passed, 2 skipped, 5 xfailed, 1 xpassed
- **Duration**: 60.41s
- **Coverage**: 51.59% (required: 46.0%)

## Warnings

- 48 warnings (mostly deprecation warnings for `datetime.utcnow()` and `_assert_not_agent_context`)
- 1 RuntimeWarning about unawaited coroutines in `test_qa_engine.py` (pre-existing)

## Files Changed

No files were modified by this step — this was a quality validation gate run only.