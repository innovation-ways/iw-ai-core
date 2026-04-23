# I-00034 S10 QV Fix Cycle 1/5

Quality gate S10 for work item I-00034 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 3 integration tests failed: (1) dashboard/CLAUDE.md missing alembic reference, (2-3) downgrade migrations not dropping iw_core_instance table

**Command output**:
```
...(truncated)...
-core/.worktrees/I-00034/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
    warnings.warn(

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00034/tests/integration/test_oss_migration.py:218: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00034/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x71d350be4590> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x71d3d39c7ec0>
    db_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_agent_constraints_coverage.py::test_claude_md_references_migrations_policy
FAILED tests/integration/test_db_identity_integration.py::TestMigrationRoundtrip::test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid
FAILED tests/integration/test_iw_core_instance_migration.py::test_downgrade_and_upgrade_round_trip
====== 3 failed, 799 passed, 7 skipped, 30 warnings in 115.58s (0:01:55) =======
make: *** [Makefile:39: test-integration] Error 1
[0m
**FAIL** - 3 tests failed:

1. `test_claude_md_references_migrations_policy` - `dashboard/CLAUDE.md` does not mention alembic
2. `test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid` - Table not dropped after downgrade  
3. `test_downgrade_and_upgrade_round_trip` - Same downgrade issue

799 passed, 3 failed, 7 skipped.
[0m$ [0muv run iw step-fail I-00034 --step S10 --reason "3 integration tests failed: (1) dashboard/CLAUDE.md missing alembic reference, (2-3) downgrade migrations not dropping iw_core_instance table"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed I-00034 step S10: 3 integration tests failed: (1) dashboard/CLAUDE.md missing alembic reference, (2-3) downgrade migrations not dropping iw_core_instance table
[0m
Gate **FAIL**. The 3 failures are unrelated to I-00034's feature work — they're pre-existing issues:
- `dashboard/CLAUDE.md` needs an alembic reference
- Two migration roundtrip tests expect `alembic downgrade -1` to drop the `iw_core_instance` table, but it doesn't

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
