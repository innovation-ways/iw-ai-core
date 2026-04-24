# F-00059 S11 QV Gate Report

## Gate
- **Name**: integration-tests
- **Command**: `make test-integration`
- **Status**: PASS

## Results
- **Tests**: 969 passed, 10 skipped, 35 warnings
- **Duration**: 155.18s (2m 35s)
- **Exit code**: 0

## Summary
Integration tests suite executed successfully against a PostgreSQL testcontainer. All database models, ORM operations, dashboard routes, OSS boundaries, migrations, and workflow logic passed. No regressions detected.

## Observations
- 2 tests skipped: `test_running_steps_query_count_bounded` and `test_second_call_within_ttl_returns_same_dirty_count` — these are expected (conditional TTL/cache tests)
- Warnings are deprecation notices from third-party libs (llama_index, starlette) and custom pytest marks — not test failures
