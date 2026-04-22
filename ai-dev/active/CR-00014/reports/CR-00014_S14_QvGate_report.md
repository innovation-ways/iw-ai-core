# CR-00014 S14 Quality Gate Report

## Gate: integration-tests
**Command:** `make test-integration`

## Result: PASS

## Summary
Integration test suite passed successfully with 762 tests passed, 7 skipped, and 30 warnings.

## Test Results
- **Total:** 762 passed
- **Skipped:** 7
- **Warnings:** 30 (deprecation warnings, no failures)
- **Duration:** 92.31s

## Key Test Coverage
- Dashboard routes and templates
- Database models and migrations
- Doc automation (merge hooks, linting, stale detection)
- Doc generation lifecycle
- OSS boundary scanning
- Code index pipeline
- Project onboarding
- Search functionality
- SSE events
- Fix cycle handling

## Files Changed
No files modified by this step. This was a pure verification gate.