# I-00038 S10 QV Fix Cycle 1/5

Quality gate S10 for work item I-00038 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Integration tests failed with schema mismatch: column 'base_sha' does not exist in project_oss_job table. 53 failures due to ORM model having columns not present in DB schema.

**Command output**:
```
...(truncated)...
egration/test_oss_migration.py::TestOssCascadeDeletes::test_delete_scan_cascades_to_findings
FAILED tests/integration/test_oss_migration.py::TestOssCascadeDeletes::test_delete_scan_cascades_to_tool_runs
FAILED tests/integration/test_oss_migration.py::TestOssRelationships::test_oss_scan_findings_relationship
FAILED tests/integration/test_oss_persistence.py::TestPersistFindings::test_persist_findings_round_trip
FAILED tests/integration/test_project_oss_job_migration.py::TestProjectOssJobORMModel::test_insert_scan_job
FAILED tests/integration/test_project_oss_job_migration.py::TestProjectOssJobORMModel::test_insert_all_fields
FAILED tests/integration/test_project_oss_job_migration.py::TestProjectOssJobORMModel::test_insert_prepare_job_with_worktree
FAILED tests/integration/test_project_oss_job_migration.py::TestProjectOssJobORMModel::test_insert_install_job
FAILED tests/integration/test_project_oss_job_migration.py::TestProjectOssJobORMModel::test_complete_job
FAILED tests/integration/test_project_oss_job_migration.py::TestProjectOssJobORMModel::test_error_job
FAILED tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_to_project
FAILED tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_invalid_project_id
FAILED tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_scan_id
FAILED tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_scan_id_set_null_on_delete
FAILED tests/integration/test_project_oss_job_migration.py::TestProjectOssJobCascadeDeletes::test_delete_project_cascades_to_jobs
FAILED tests/integration/test_project_oss_job_migration.py::TestProjectOssJobRelationships::test_project_oss_jobs_relationship
===== 53 failed, 917 passed, 10 skipped, 52 warnings in 176.27s (0:02:56) ======
make: *** [Makefile:39: test-integration] Error 1
[0m
[0m$ [0mmkdir -p ai-dev/active/I-00038/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/I-00038/reports/I-00038_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail I-00038 --step S10 --reason "Integration tests failed with schema mismatch: column 'base_sha' does not exist in project_oss_job table. 53 failures due to ORM model having columns not present in DB schema."
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed I-00038 step S10: Integration tests failed with schema mismatch: column 'base_sha' does not exist in project_oss_job table. 53 failures due to ORM model having columns not present in DB schema.
[0m
**FAIL** - Integration tests failed with 53 failures.

Root cause: `psycopg.errors.UndefinedColumn: column "base_sha" of relation "project_oss_job" does not exist` — the `ProjectOssJob` ORM model has columns not present in the actual database schema.

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
