# F-00072 S09 QvGate Report — unit-tests

## Gate
- **Gate**: unit-tests
- **Command**: `make test-unit`
- **Result**: PASS

## Summary
Ran full unit test suite via `make test-unit`. All tests passed.

## Results
- **Passed**: 2072
- **Skipped**: 2
- **Warnings**: 48 (deprecation warnings from datetime.utcnow(), async mock warnings, etc. — not failures)
- **Exit code**: 0

## Files Changed
None — this was a quality validation gate only, no code changes.

## Observations
- Deprecation warnings from `datetime.utcnow()` are present in several test files but do not cause failures.
- Async mock warnings in `test_qa_engine.py` are also present but do not affect test outcomes.
- No test failures or errors.
