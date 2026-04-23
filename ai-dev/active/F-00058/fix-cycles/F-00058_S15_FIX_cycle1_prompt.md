# F-00058 S15 QV Fix Cycle 1/5

Quality gate S15 for work item F-00058 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: integration-tests gate failed: 23 failed, 393 errors out of 929 total (513 passed). Errors dominated by orch.dbc.ExecutableNotFoundError suggesting testcontainer/infra issues.

**Command output**:
```
...(truncated)...

ERROR tests/integration/test_project_onboarding_api.py::TestBrowseDirectoryRoute::test_has_breadcrumbs
ERROR tests/integration/test_project_onboarding_api.py::TestBrowseDirectoryRoute::test_has_directory_entries_section
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
===== 23 failed, 513 passed, 45 warnings, 393 errors in 235.80s (0:03:55) ======
make: *** [Makefile:39: test-integration] Error 1
[0m
[0m$ [0mmkdir -p ai-dev/active/F-00058/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00058/reports/F-00058_S15_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00058 --step S15 --reason "integration-tests gate failed: 23 failed, 393 errors out of 929 total (513 passed). Errors dominated by orch.dbc.ExecutableNotFoundError suggesting testcontainer/infra issues."
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00058 step S15: integration-tests gate failed: 23 failed, 393 errors out of 929 total (513 passed). Errors dominated by orch.dbc.ExecutableNotFoundError suggesting testcontainer/infra issues.
[0m
**FAIL** — `make test-integration` exited with code 1.

**Results**: 23 failed, 513 passed, 393 errors in 235.80s

The majority of errors are `orch.dbc.ExecutableNotFoundError` / `ModuleNotFoundError` across API, dashboard, OSS, and doc routes — indicating systemic test infrastructure issues (likely testcontainer startup or import path problems) rather than a single code regression. The 513 passed tests show core ORM functionality is intact.

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
