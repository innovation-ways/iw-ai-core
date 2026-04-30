# F-00073 S11 QV Gate Report

**Gate**: smoke
**Command**: `make smoke`
**Result**: PASS

## Summary

Ran smoke test suite via `make smoke`. 13 tests passed, 2 xfailed (expected failures), 2 warnings.

## Test Results

| Test | Status |
|------|--------|
| test_batch_create_independent_items_all_group_0 | PASSED |
| test_project_dashboard_returns_200 | PASSED |
| test_queue_returns_200 | PASSED |
| test_history_returns_200 | PASSED |
| test_healthz_identity_200_on_match | PASSED |
| test_healthz_identity_503_on_mismatch | PASSED |
| test_healthz_identity_200_on_bootstrap | PASSED |
| test_missing_coverage_json | PASSED |
| test_sighup_handler_sets_stale_mtime | PASSED |
| test_iw_help_exits_zero | PASSED |
| test_base_import_works | PASSED |
| test_dashboard_app_factory_creates | PASSED |
| test_root_projects_page_renders | PASSED |
| test_db_url_construction_redacts_password | XFAIL |
| test_get_orch_db_url_redacts_password | XFAIL |

## Warnings

- Unknown pytest config option `env` ( harmless)
- TestRunStatus collector warning (enum without test interest)

## Conclusion

All 13 smoke tests passed. Gate PASSED.