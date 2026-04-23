# I-00034 S10 QV Fix Cycle 3/5

Quality gate S10 for work item I-00034 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Integration tests failed: 2 failed assertions in migration tests, 352 errors due to DB instance identity mismatch

**Command output**:
```
...(truncated)...
irectoryRoute::test_has_directory_entries_section
ERROR tests/integration/test_project_onboarding_api.py::TestBrowseDirectoryRoute::test_show_hidden_param_accepted
ERROR tests/integration/test_project_onboarding_api.py::TestBrowseDirectoryRoute::test_path_param_filters_entries
ERROR tests/integration/test_project_onboarding_api.py::TestBrowseDirectoryRoute::test_navigates_to_subdirectory
ERROR tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_missing_project_id_returns_modal_with_error
ERROR tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_invalid_project_id_returns_modal_with_error
ERROR tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_duplicate_project_id_returns_error
ERROR tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_missing_display_name_returns_error
ERROR tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_nonexistent_repo_root_returns_error
ERROR tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_valid_repo_without_git_returns_error
ERROR tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_valid_creation_redirects
ERROR tests/integration/test_project_onboarding_api.py::TestCreateProjectRoute::test_project_created_in_db
====== 2 failed, 455 passed, 29 warnings, 352 errors in 177.89s (0:02:57) ======
make: *** [Makefile:39: test-integration] Error 1
[0m
**FAIL** - Integration tests failed with exit code 1.

**Summary:**
- 2 failed tests (migration downgrade tests - table not dropped after downgrade)
- 352 errors (mostly `InstanceMismatchError` - tests connecting to wrong DB instance)
- 455 passed

**Root cause:** Many tests are hitting `InstanceMismatchError` because `IW_CORE_EXPECTED_INSTANCE_ID` is set in `.env` but tests are using a different DB instance. Also, the migration downgrade doesn't actually drop the `iw_core_instance` table as expected.
[0m← [0mWrite ai-dev/active/I-00034/reports/I-00034_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail I-00034 --step S10 --reason "Integration tests failed: 2 failed assertions in migration tests, 352 errors due to DB instance identity mismatch"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed I-00034 step S10: Integration tests failed: 2 failed assertions in migration tests, 352 errors due to DB instance identity mismatch
[0m
**FAIL** - Integration tests failed with 2 failed tests and 352 errors.

Key issues:
- 2 migration tests fail because `alembic downgrade -1` doesn't drop the `iw_core_instance` table as expected
- 352 errors all share `InstanceMismatchError` - tests are hitting the live DB instead of testcontainers

Report written to `ai-dev/active/I-00034/reports/I-00034_S10_QvGate_report.md`.

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
