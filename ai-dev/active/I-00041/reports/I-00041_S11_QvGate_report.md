# I-00041 S11 QV Gate Report: unit-tests

## Gate
- **Command**: `make test-unit`
- **Result**: FAIL

## Summary
42 test failures out of 1637 tests (1632 passed, 2 skipped).

## Failing Test Categories

1. **live_db_guard semantics tests** (~28 failures)
   - `test_safe_migrate.py`: Tests expecting `AgentContextForbiddenError` receive `LiveDbConnectionRefusedError` instead
   - `test_safe_migrate_guards.py`: Guard behavior tests failing due to `IW_CORE_TEST_CONTEXT` + `IW_CORE_OPERATOR_APPLY` interaction

2. **Daemon/Migration tests** (7 failures)
   - `test_migration_rebase.py`: `TestEmitDaemonEvent::test_writes_daemon_event_row`, `TestWriteRebaseLog::test_writes_pending_migration_log_row`
   - `test_migration_pipeline.py`: Merge queue frozen state tests

3. **Worktree compose tests** (4 failures)
   - `test_worktree_compose.py`: Gitignored/env guard tests expecting `AssertionError` get `LiveDbConnectionRefusedError`

4. **Merge queue tests** (7 failures)
   - `test_merge_queue.py`, `test_merge_queue_cli.py`: Merge queue processing tests

## Root Cause
`IW_CORE_OPERATOR_APPLY=true` was set in the parent shell environment before running `make test-unit`. This flag propagates to subprocess calls (git, docker compose) and modifies the `live_db_guard` decision matrix:

```
2. Any allowed-context flag is set → ALLOW (operator/daemon)
     - IW_CORE_OPERATOR_APPLY=true  ← inherited from shell
```

When tests patch `IW_CORE_AGENT_CONTEXT=true` and also inherit `IW_CORE_TEST_CONTEXT=true` (from Makefile) and `IW_CORE_OPERATOR_APPLY=true` (from shell), the guard logic produces `LiveDbConnectionRefusedError` instead of the expected `AgentContextForbiddenError`.

## Files Changed
None - this is a pre-existing code issue exposed by environment context.

## Recommendation
Run unit tests without `IW_CORE_OPERATOR_APPLY=true` in the shell environment to verify if failures are environmental:
```bash
unset IW_CORE_OPERATOR_APPLY
make test-unit
```
