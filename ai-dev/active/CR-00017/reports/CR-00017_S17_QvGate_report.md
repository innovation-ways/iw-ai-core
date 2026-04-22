# CR-00017 S17 QV Gate Report

## Gate: unit-tests

**Command:** `make test-unit`

**Result:** PASS

## Summary

Ran the full unit test suite (1232 tests) via `make test-unit`.

- **Tests passed:** 1232
- **Tests failed:** 0
- **Warnings:** 18 (deprecation warnings and async mock warnings — not errors)

Exit code: 0

## Files Changed

No files were modified as part of this step. The gate simply executed the existing unit test suite.

## Observations

- All 1232 tests passed in 8.56 seconds.
- 18 warnings are present (mostly deprecation warnings about `datetime.utcnow()` and async mock coroutines not being awaited) — these are pre-existing and do not constitute failures.
- No test files were modified; no code changes introduced.