# I-00045 S10 QV Gate Report

## Gate: integration-tests
**Command**: `make allure-integration`
**Result**: PASS

## Summary

Ran the full integration test suite via `make allure-integration`. All tests passed.

## Test Results

- **Total**: 1134 passed, 11 skipped
- **Duration**: 233.55s (3m 53s)
- **Exit code**: 0

## Key Test Coverage

- OSS publish, dashboard routes, dashboard service, SSE, templates, findings, freshness, persistence, scanner
- Project docs, onboarding API, worktree isolation
- Code index pipeline, doc index pipeline
- Migration pipeline, parallel migrations, rebase
- Work item evidence, search, SSE events, step monitor lifecycle
- Boundary behavior, invariants, QA v2 regression

## Issues/Observations

- 153 warnings (deprecation notices for `table_names()`, `datetime.utcnow()`, etc.) — not blockers
- 11 skipped tests (expected)