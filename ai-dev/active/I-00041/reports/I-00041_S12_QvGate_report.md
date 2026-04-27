# I-00041 S12 QV Gate Report

## Gate: integration-tests
**Command**: `make allure-integration`
**Result**: FAIL (exit code 1)

## Summary

Ran the integration test suite via `make allure-integration`. The suite executed 1104 tests (1090 passed, 4 failed, 11 skipped) in approximately 3.5 minutes.

## Failures (4)

All 4 failures are `LiveDbConnectionRefusedError` in tests that call `is_merge_queue_frozen()` or similar daemon code paths that attempt to connect to the live orch DB:

1. `tests/integration/test_batch_manager.py::TestMergeQueueIntegration::test_merge_queue_oldest_first`
2. `tests/integration/test_batch_manager.py::TestMergeQueueIntegration::test_merge_queue_one_at_a_time`
3. `tests/integration/test_daemon_restart_reattach.py::test_daemon_restart_reattaches_to_running_stack`
4. `tests/integration/test_migration_rebase_conflict.py::test_ac7_queue_not_frozen_after_migration_invalid`

**Root cause**: These tests invoke daemon code (`is_merge_queue_frozen()`, `worktree_compose.up()`) which internally calls `safe_create_engine()` → `assert_engine_url_allowed()`. When `IW_CORE_TEST_CONTEXT=true` and the URL matches the live DB, the guard raises `LiveDbConnectionRefusedError`. This is a pre-existing test infrastructure issue — the tests call into daemon paths that are not compatible with the live DB guard when in test context.

## Files Changed

None. This step only ran existing tests.

## Observations

- 1090 integration tests pass successfully
- The 4 failures are all in tests that exercise daemon-side merge queue and worktree compose functionality from an integration test context
- These failures appear to be pre-existing issues with the test infrastructure, not introduced by any recent change
- The `live_db_guard` is functioning as designed (blocking live DB connections from test context), but these particular tests need either mocking or a different approach to test the daemon code paths