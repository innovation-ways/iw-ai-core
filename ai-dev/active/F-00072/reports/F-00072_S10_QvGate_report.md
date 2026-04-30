# F-00072 S10 QvGate Report

## Gate: integration-tests
**Command**: `make allure-integration`
**Result**: PASS

## Summary

Ran the full integration test suite with Allure reporting.

## Test Results

- **1161 tests passed**
- **11 tests skipped**
- **0 tests failed**
- **154 warnings** (deprecation notices, no functional impact)

Total runtime: 278.74s (4m 38s)

All tests passed including OSS dashboard, project onboarding, RAG index generation, work item evidence, SSE events, and migration tests.

## Observations

- Several deprecation warnings related to `table_names()` (should be `list_tables()` in newer LanceDB) — non-blocking
- Minor SQLAlchemy transaction warnings in a handful of FK-constraint tests — expected behavior being tested
- No new regressions detected