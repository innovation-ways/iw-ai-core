# S19 QV Gate Report — integration-tests

## Gate
- **Command**: `make test-integration`
- **Result**: FAIL

## Summary

The integration test suite ran successfully with **1073 tests passing** and only **1 error**:

```
ERROR tests/integration/test_worktree_reaper_real_containers.py::test_reaper_classifies_and_reaps_orphan
```

**Root cause**: The `db_engine` fixture in `tests/integration/conftest.py` runs `FTS_TRIGGER_SQL` on every test session. When the `test_worktree_reaper_real_containers.py` test runs in the same test session as prior tests that already created the `trg_work_items_fts` trigger, the trigger creation fails with:

```
psycopg.errors.DuplicateObject: trigger "trg_work_items_fts" for relation "work_items" already exists
```

This is a **fixture/test isolation issue** — the FTS trigger setup is not idempotent and does not check for existence before creating.

## Files Changed
None — this is a pre-existing test infrastructure issue, not a code regression introduced by F-00062.

## Observations
- The error occurs at **setup** of the last test (`test_reaper_classifies_and_reaps_orphan`), not during execution.
- 1073 tests passed, 10 skipped, 1 error.
- The trigger setup in `conftest.py:113` runs `CREATE TRIGGER` without `IF NOT EXISTS` or a `DROP IF EXISTS` guard.
- This issue likely existed before F-00062 and is unrelated to the feature being implemented.