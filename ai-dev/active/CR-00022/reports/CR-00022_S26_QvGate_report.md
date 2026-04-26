# CR-00022 S26 QvGate Report

## Gate: integration-tests
**Command**: `make test-integration`

## Result: PASS

## Summary

Executed full integration test suite with real Docker containers (testcontainers). All tests passed.

**Test Results**: 1090 passed, 10 skipped, 154 warnings
**Duration**: 3m 33s

## Warnings Notes

The following warnings were observed but do not affect the gate result:
- Deprecation warnings for `table_names()` (use `list_tables()` instead) in LanceDB integration
- Deprecation warnings for `datetime.utcnow()` (use timezone-aware objects)
- SAWarning about transaction rollback in some tests (benign, test isolation cleanup)
- PytestUnknownMarkWarning for `@pytest.mark.slow` (custom mark not registered)

## Key Test Areas Covered

- Work item evidence and FTS
- Project OSS job migration
- OSS dashboard routes, SSE, and service
- Project onboarding API
- Doc generation jobs
- Code index pipeline
- Doc index poller and job runner
- RAG / semantic search (F00060 invariants)
- Migration pipeline (parallel migrations, rebase)
- Worktree reaper