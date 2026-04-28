# I-00044 S10 QvGate Report

## Gate: integration-tests
**Command**: `make allure-integration`
**Result**: PASS

## Summary

Ran the full integration test suite via `make allure-integration`. All 1134 tests passed (11 skipped). The test run completed in 3 minutes 54 seconds.

## Test Results

- **Total**: 1134 passed
- **Skipped**: 11
- **Warnings**: 153 (deprecation warnings from third-party libs, no action required)
- **Duration**: 234.34s

Notable test groups that all passed:
- OSS publish, dashboard boundary, dashboard routes, dashboard service
- SSE events, job event streams, heartbeat
- Migration tests (oss, project_oss_job, pending_migration_log, parallel_migrations)
- Project docs, search, work item evidence, functional doc FTS
- Code index pipeline, doc indexer, doc index poller
- Worktree reaper, per-worktree isolation

## Observations

- No test failures
- Deprecation warnings are from upstream libraries (lancedb, llama_index, starlette) and Python stdlib (datetime.utcnow, table_names())
- All tests clean — no regressions detected