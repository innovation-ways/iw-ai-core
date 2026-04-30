# F-00073 S10 QV Fix Cycle 3/5

Quality gate S10 for work item F-00073 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Integration tests timed out after 300 seconds (exit code 143 - SIGTERM). Partial test run completed many tests successfully before timeout.

**Command output**:
```
...(truncated)...
ViewsInvariant::test_quality_page_loads_without_oss_errors PASSED [ 81%]
tests/integration/test_oss_dashboard_templates_extras.py::TestNoRegressionsSiblingViewsInvariant::test_documentation_page_loads_without_oss_errors PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestPersistDetails::test_detail_rows_created PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestPersistDetails::test_evidence_json_strips_results PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestPersistDetails::test_no_results_means_no_detail_rows PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestPersistDetails::test_cascade_delete_on_finding PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_returns_paginated_results PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_default_limit PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_capped_flag_propagated PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_404_when_finding_unknown PASSED [ 82%]
tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_404_when_finding_belongs_to_other_project PASSED [ 82%]
tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_no_detail_table_returns_empty PASSED [ 82%]
tests/integration/test_oss_finding_details.py::TestSchema::test_oss_finding_detail_table_exists PASSED [ 82%]
tests/integration/test_oss_freshness.py::TestOssFreshness::test_stale_detection_after_commit make: *** [Makefile:59: allure-integration] Error 143


<bash_metadata>
bash tool terminated command after exceeding timeout 300000 ms. If this command is expected to take longer and is not waiting for interactive input, retry with a larger timeout value in milliseconds.
</bash_metadata>
[0m
[0m$ [0mls -la ai-dev/active/F-00073/ 2>/dev/null || echo "dir not found"
total 44
drwxrwxr-x  6 sergiog sergiog  4096 Apr 30 10:48 .
drwxrwxr-x 15 sergiog sergiog  4096 Apr 30 09:42 ..
drwxrwxr-x  3 sergiog sergiog  4096 Apr 30 09:42 F-00073
-rw-rw-r--  1 sergiog sergiog 13857 Apr 30 09:42 F-00073_Feature_Design.md
drwxrwxr-x  2 sergiog sergiog  4096 Apr 30 11:08 fix-cycles
drwxrwxr-x  2 sergiog sergiog  4096 Apr 30 09:42 prompts
drwxrwxr-x  2 sergiog sergiog  4096 Apr 30 10:57 reports
-rw-rw-r--  1 sergiog sergiog  2456 Apr 30 09:42 workflow-manifest.json
[0m
[0m$ [0mmkdir -p ai-dev/active/F-00073/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00073/reports/F-00073_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00073 --step S10 --reason "Integration tests timed out after 300 seconds (exit code 143 - SIGTERM). Partial test run completed many tests successfully before timeout."
Failed F-00073 step S10: Integration tests timed out after 300 seconds (exit code 143 - SIGTERM). Partial test run completed many tests successfully before timeout.
[0m

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
