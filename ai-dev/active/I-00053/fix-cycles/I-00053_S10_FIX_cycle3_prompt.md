# I-00053 S10 QV Fix Cycle 3/5

Quality gate S10 for work item I-00053 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: integration-tests failed: exit=143 — test run killed by 5-minute timeout at test_oss_freshness.py::TestOssFreshness::test_stale_detection_after_commit

**Command output**:
```
...(truncated)...
ASSED [ 80%]
tests/integration/test_oss_dashboard_templates_extras.py::TestCliBlockRemoved::test_no_publish_cli_block PASSED [ 80%]
tests/integration/test_oss_dashboard_templates_extras.py::TestNoRegressionsSiblingViewsInvariant::test_code_page_loads_without_oss_errors PASSED [ 80%]
tests/integration/test_oss_dashboard_templates_extras.py::TestNoRegressionsSiblingViewsInvariant::test_tests_page_loads_without_oss_errors PASSED [ 80%]
tests/integration/test_oss_dashboard_templates_extras.py::TestNoRegressionsSiblingViewsInvariant::test_quality_page_loads_without_oss_errors PASSED [ 80%]
tests/integration/test_oss_dashboard_templates_extras.py::TestNoRegressionsSiblingViewsInvariant::test_documentation_page_loads_without_oss_errors PASSED [ 80%]
tests/integration/test_oss_finding_details.py::TestPersistDetails::test_detail_rows_created PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestPersistDetails::test_evidence_json_strips_results PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestPersistDetails::test_no_results_means_no_detail_rows PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestPersistDetails::test_cascade_delete_on_finding PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_returns_paginated_results PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_default_limit PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_capped_flag_propagated PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_404_when_finding_unknown PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_404_when_finding_belongs_to_other_project PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestFindingDetailsRoute::test_no_detail_table_returns_empty PASSED [ 81%]
tests/integration/test_oss_finding_details.py::TestSchema::test_oss_finding_detail_table_exists PASSED [ 81%]
tests/integration/test_oss_freshness.py::TestOssFreshness::test_stale_detection_after_commit make: *** [Makefile:54: allure-integration] Error 143
[0m
[0m$ [0mmkdir -p ai-dev/active/I-00053/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/I-00053/reports/I-00053_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail I-00053 --step S10 --reason "integration-tests failed: exit=143 — test run killed by 5-minute timeout at test_oss_freshness.py::TestOssFreshness::test_stale_detection_after_commit"
Failed I-00053 step S10: integration-tests failed: exit=143 — test run killed by 5-minute timeout at test_oss_freshness.py::TestOssFreshness::test_stale_detection_after_commit
[0m
```json
{
  "step": "S10",
  "agent": "qv-gate",
  "work_item": "I-00053",
  "gate": "integration-tests",
  "command": "make allure-integration",
  "exit_code": 143,
  "result": "fail",
  "report": "ai-dev/active/I-00053/reports/I-00053_S10_QvGate_report.md"
}
```

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
