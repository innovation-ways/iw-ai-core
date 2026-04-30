# F-00073 S06 QvGate Report

## Gate: lint
**Command**: `make lint`
**Result**: FAIL

## Issues Found

8 lint errors in `dashboard/routers/tests.py` and `tests/integration/daemon/test_baseline_qv_pipeline.py`:

- **PT028** (6 errors): Test function parameters with default arguments (`db`, `tab`) in `dashboard/routers/tests.py:88,89,131,152,170,190,219`
- **UP037** (1 error): Unnecessary quotes in type annotation `"MockPopen"` in `tests/integration/daemon/test_baseline_qv_pipeline.py:688`

## Action Taken

All 8 errors are auto-fixable with `ruff check --fix`. Applied the fix.

## Files Changed

- `dashboard/routers/tests.py` — removed default args from test function parameters
- `tests/integration/daemon/test_baseline_qv_pipeline.py` — removed quotes from type annotation

## Verification

Re-ran `make lint` after fix — **PASS** (exit code 0, no errors).