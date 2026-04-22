# CR-00017 S18 QV Fix Cycle 2/5

Quality gate S18 for work item CR-00017 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 3 integration test failures: test_history_returns_paginated_items (pagination), test_downgrade_and_upgrade_round_trip (alembic downgrade), test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid (alembic downgrade)

**Command output**:
```
...(truncated)...
_oss_scan_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00017/tests/integration/test_oss_migration.py:218: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00017/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7ac3ac46b2c0> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x7ac3ae3f3a70>
    db_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_dashboard_remaining.py::test_history_returns_paginated_items
FAILED tests/integration/test_db_identity_integration.py::TestMigrationRoundtrip::test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid
FAILED tests/integration/test_iw_core_instance_migration.py::test_downgrade_and_upgrade_round_trip
====== 3 failed, 793 passed, 7 skipped, 30 warnings in 113.08s (0:01:53) =======
make: *** [Makefile:39: test-integration] Error 1
[0m
**FAIL** — 3 tests failed out of 793.

Failures:
- `test_history_returns_paginated_items` — pagination assertion (I-00025 not in page 1)
- `test_downgrade_and_upgrade_round_trip` — alembic downgrade not dropping table
- `test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid` — same downgrade issue

Now writing the report and calling step-fail:
[0m$ [0mmkdir -p ai-dev/active/CR-00017/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/CR-00017/reports/CR-00017_S18_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail CR-00017 --step S18 --reason "3 integration test failures: test_history_returns_paginated_items (pagination), test_downgrade_and_upgrade_round_trip (alembic downgrade), test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid (alembic downgrade)"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00017 step S18: 3 integration test failures: test_history_returns_paginated_items (pagination), test_downgrade_and_upgrade_round_trip (alembic downgrade), test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid (alembic downgrade)
[0m
**FAIL** — `make test-integration` returned exit code 1.

3 failures from 793 tests:
- `test_history_returns_paginated_items` — pagination assertion (I-00025 missing from page 1)
- `test_downgrade_and_upgrade_round_trip` — alembic downgrade doesn't drop `iw_core_instance` table
- `test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid` — same downgrade issue

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
