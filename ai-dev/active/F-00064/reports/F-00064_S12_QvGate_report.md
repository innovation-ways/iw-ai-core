# F-00064 S12 QV Gate Report

## Gate: integration-tests
**Command**: `make test-integration`
**Result**: PASS

## Summary

Ran the full integration test suite (1134 passed, 11 skipped, 153 warnings).

## Output

- 1134 passed
- 11 skipped
- 153 warnings (deprecation notices, mostly from lancedb and datetime.utcnow())
- Duration: 260.75s (4m20s)

## Warnings

Most warnings are deprecations in third-party libraries (lancedb `table_names()`, `datetime.utcnow()`, starlette TestClient timeout). No test failures or errors.

## No files changed