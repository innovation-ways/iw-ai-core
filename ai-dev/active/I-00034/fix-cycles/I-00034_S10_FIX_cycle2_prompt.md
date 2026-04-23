# I-00034 S10 QV Fix Cycle 2/5

Quality gate S10 for work item I-00034 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 352 errors mostly due to DB identity mismatch (live DB instance ID does not match IW_CORE_EXPECTED_INSTANCE_ID in .env); 2 migration downgrade tests also fail

**Command output**:
```
...(truncated)...
toryRoute::test_has_directory_entries_section
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
====== 2 failed, 455 passed, 29 warnings, 352 errors in 185.87s (0:03:05) ======
make: *** [Makefile:39: test-integration] Error 1
[0m
**FAIL** — Integration tests failed with exit code 1.

- 2 test failures (downgrade not dropping table)
- 352 errors, mostly `InstanceMismatchError` (dashboard lifespan hitting live DB instead of testcontainer)
- 455 passed, 29 warnings
[0m$ [0mmkdir -p ai-dev/active/I-00034/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/I-00034/reports/I-00034_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail I-00034 --step S10 --reason "352 errors mostly due to DB identity mismatch (live DB instance ID does not match IW_CORE_EXPECTED_INSTANCE_ID in .env); 2 migration downgrade tests also fail"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed I-00034 step S10: 352 errors mostly due to DB identity mismatch (live DB instance ID does not match IW_CORE_EXPECTED_INSTANCE_ID in .env); 2 migration downgrade tests also fail
[0m
**FAIL** (exit code 1)

- 455 passed, 2 failed, 352 errors
- Root cause: `InstanceMismatchError` — the DB instance ID (`08446ded-daba-4e08-9721-3046dc68efa0`) does not match `IW_CORE_EXPECTED_INSTANCE_ID` in `.env` (`518ac56a-36f7-4c43-8f53-cfbb8a6baa3e`). This crashes the FastAPI app lifespan, causing setup failures for most tests.
- 2 actual failures are migration downgrade tests (table not dropped when expected).

Report saved at `ai-dev/active/I-00034/reports/I-00034_S10_QvGate_report.md`.

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
