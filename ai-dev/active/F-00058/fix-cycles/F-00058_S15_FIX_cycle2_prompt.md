# F-00058 S15 QV Fix Cycle 2/5

Quality gate S15 for work item F-00058 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Integration tests failed: 23 failed, 37 errors. Root cause: OSS tables (project_oss_job, oss_scan, oss_finding, oss_tool_run) missing from test schema - migration not applied to testcontainers.

**Command output**:
```
...(truncated)...
an_id
ERROR tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_to_project
ERROR tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
ERROR tests/integration/test_oss_migration.py::TestOssCascadeDeletes::test_delete_project_cascades_to_scans
ERROR tests/integration/test_oss_migration.py::TestOssCascadeDeletes::test_delete_scan_cascades_to_findings
ERROR tests/integration/test_oss_migration.py::TestOssCascadeDeletes::test_delete_scan_cascades_to_tool_runs
ERROR tests/integration/test_oss_migration.py::TestOssRelationships::test_project_oss_scans_relationship
ERROR tests/integration/test_oss_migration.py::TestOssRelationships::test_oss_scan_findings_relationship
ERROR tests/integration/test_oss_migration.py::TestOssRelationships::test_oss_scan_tool_runs_relationship
ERROR tests/integration/test_oss_migration.py::TestProjectOssEnabled::test_project_oss_enabled_default
ERROR tests/integration/test_oss_migration.py::TestProjectOssEnabled::test_project_oss_enabled_can_be_set
ERROR tests/integration/test_oss_migration.py::TestOssMigrationDowngrade::test_downgrade_drops_tables
ERROR tests/integration/test_oss_persistence.py::TestPersistFindings::test_persist_findings_round_trip
ERROR tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row
= 23 failed, 858 passed, 7 skipped, 46 warnings, 37 errors in 168.78s (0:02:48) =
make: *** [Makefile:39: test-integration] Error 1
[0m
[0m$ [0mmkdir -p ai-dev/active/F-00058/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00058/reports/F-00058_S15_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00058 --step S15 --reason "Integration tests failed: 23 failed, 37 errors. Root cause: OSS tables (project_oss_job, oss_scan, oss_finding, oss_tool_run) missing from test schema - migration not applied to testcontainers."
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00058 step S15: Integration tests failed: 23 failed, 37 errors. Root cause: OSS tables (project_oss_job, oss_scan, oss_finding, oss_tool_run) missing from test schema - migration not applied to testcontainers.
[0m
**FAIL** — `make test-integration` returned exit code 1.

**Result**: 23 failed, 858 passed, 7 skipped, 46 warnings, **37 errors** in 168.78s.

The test failures are concentrated in OSS-related tests. The core issue is that `project_oss_job` (and related OSS tables `oss_scan`, `oss_finding`, `oss_tool_run`) do not exist in the test schema — the ORM models are defined but the corresponding migration has not been applied to the testcontainers. Background threads spawned by the OSS service hit `UndefinedTable` errors when trying to query these missing tables.

Report written to `ai-dev/active/F-00058/reports/F-00058_S15_QvGate_report.md`.

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
