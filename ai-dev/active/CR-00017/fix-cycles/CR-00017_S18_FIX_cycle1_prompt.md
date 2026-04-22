# CR-00017 S18 QV Fix Cycle 1/5

Quality gate S18 for work item CR-00017 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 4 integration test failures: test_merge_queue_oldest_first (ValueError converting B001 to int), test_history_returns_paginated_items (pagination assertion), test_downgrade_and_upgrade_round_trip (iw_core_instance table not dropped), test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid (same)

**Command output**:
```
...(truncated)...
Doc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x71d6037d4f50>
    db_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_batch_manager.py::TestMergeQueueIntegration::test_merge_queue_oldest_first
FAILED tests/integration/test_dashboard_remaining.py::test_history_returns_paginated_items
FAILED tests/integration/test_db_identity_integration.py::TestMigrationRoundtrip::test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid
FAILED tests/integration/test_iw_core_instance_migration.py::test_downgrade_and_upgrade_round_trip
====== 4 failed, 792 passed, 7 skipped, 30 warnings in 116.74s (0:01:56) =======
make: *** [Makefile:39: test-integration] Error 1
[0m
**FAIL** - 4 failures in 792 passed tests.

Key failures:
1. `test_merge_queue_oldest_first`: `ValueError: invalid literal for int() with base 10: 'B001'` at `merge_queue.py:189`
2. `test_history_returns_paginated_items`: Assertion error - item `I-00025` not appearing in paginated history
3. `test_downgrade_and_upgrade_round_trip` / `test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid`: Alembic downgrade not dropping `iw_core_instance` table as expected
[0m$ [0mmkdir -p ai-dev/active/CR-00017/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/CR-00017/reports/CR-00017_S18_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail CR-00017 --step S18 --reason "4 integration test failures: test_merge_queue_oldest_first (ValueError converting B001 to int), test_history_returns_paginated_items (pagination assertion), test_downgrade_and_upgrade_round_trip (iw_core_instance table not dropped), test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid (same)"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00017 step S18: 4 integration test failures: test_merge_queue_oldest_first (ValueError converting B001 to int), test_history_returns_paginated_items (pagination assertion), test_downgrade_and_upgrade_round_trip (iw_core_instance table not dropped), test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid (same)
[0m
**FAIL** — `make test-integration` returned exit code 1.

**Summary**: 792 passed, 4 failed. The failures are pre-existing issues:
1. `test_merge_queue_oldest_first` — `ValueError: invalid literal for int() with base 10: 'B001'` at `merge_queue.py:189`
2. `test_history_returns_paginated_items` — pagination assertion failure
3. `test_downgrade_and_upgrade_round_trip` — `iw_core_instance` table not dropped on downgrade
4. `test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid` — same downgrade issue

Report written to `ai-dev/active/CR-00017/reports/CR-00017_S18_QvGate_report.md`.

```


## Gate Command

The quality gate that failed runs:
```bash
make test-integration
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
