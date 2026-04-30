# F-00073 S10 QV Fix Cycle 1/5

Quality gate S10 for work item F-00073 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: make allure-integration timed out after 300s (exit 143) at ~80% through integration suite

**Command output**:
```
...(truncated)...
:test_oss_status_frame_absent_in_quality_page PASSED [ 79%]
tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_in_oss_page PASSED [ 79%]
tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_absent_in_batches_page PASSED [ 79%]
tests/integration/test_oss_dashboard_templates_extras.py::TestOssStatusFramePresenceInvariant::test_oss_status_frame_is_htmx_loaded PASSED [ 79%]
tests/integration/test_oss_dashboard_templates_extras.py::TestInstallWorktreeNullInvariant::test_install_job_has_no_worktree_columns PASSED [ 79%]
tests/integration/test_oss_dashboard_templates_extras.py::TestInstallWorktreeNullInvariant::test_worktree_columns_removed_from_schema PASSED [ 80%]
tests/integration/test_oss_dashboard_templates_extras.py::TestNoScanGrayPillInvariant::test_no_scan_renders_gray_pill_not_yet_scanned PASSED [ 80%]
tests/integration/test_oss_dashboard_templates_extras.py::TestNoScanGrayPillInvariant::test_no_scan_gray_pill_in_full_oss_page PASSED [ 80%]
tests/integration/test_oss_dashboard_templates_extras.py::TestDomainCardEmptyStateInvariant::test_no_findings_renders_empty_state_message PASSED [ 80%]
tests/integration/test_oss_dashboard_templates_extras.py::TestDomainCardEmptyStateInvariant::test_domain_card_with_findings_renders_correctly PASSED [ 80%]
tests/integration/test_oss_dashboard_templates_extras.py::TestInstallModalEnableButtonInvariant::test_enable_button_disabled_when_tools_missing PASSED [ 80%]
tests/integration/test_oss_dashboard_templates_extras.py::TestInstallModalEnableButtonInvariant::test_enable_button_enabled_when_all_tools_installed PASSED [ 80%]
tests/integration/test_oss_dashboard_templates_extras.py::TestOssTableColumnOrder::test_table_has_correct_column_headers make: *** [Makefile:59: allure-integration] Error 143


<bash_metadata>
bash tool terminated command after exceeding timeout 300000 ms. If this command is expected to take longer and is not waiting for interactive input, retry with a larger timeout value in milliseconds.
</bash_metadata>
[0m
[0m$ [0mmkdir -p ai-dev/active/F-00073/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00073/reports/F-00073_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00073 --step S10 --reason "make allure-integration timed out after 300s (exit 143) at ~80% through integration suite"
Failed F-00073 step S10: make allure-integration timed out after 300s (exit 143) at ~80% through integration suite
[0m
**FAIL** — `make allure-integration` timed out after 300s (exit 143).

The suite was ~80% complete with all visible tests passing. The timeout occurred during `test_table_has_correct_column_headers` in `test_oss_dashboard_templates_extras.py`. No test failures were observed before termination — this is a duration issue, not a correctness issue.

Report written to `ai-dev/active/F-00073/reports/F-00073_S10_QvGate_report.md`.

```


## Gate Command

The quality gate that failed runs:
```bash
make allure-integration
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
