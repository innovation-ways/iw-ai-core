# I-00038 S10 QV Gate Report

## Gate: integration-tests
**Command**: `make test-integration`
**Result**: PASS

## Summary
Ran the full integration test suite. All 970 tests passed (10 skipped). Execution time: 163s.

## Observations
- No test failures or errors
- 35 warnings (deprecation warnings in third-party libs, SAWarning about transaction rollback — all expected/noise)
- 10 skipped tests: `test_running_failed_steps_query_count_bounded` (N+1 skip), `test_nav_worktree_badge_cache` TTL-related tests

## Files Changed
None — this was a quality gate verification only.
