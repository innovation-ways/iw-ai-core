# F-00073 S10 QV Fix Cycle 2/5

Quality gate S10 for work item F-00073 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: make allure-integration timed out after 300s at ~82% through integration suite. All visible tests passed before timeout — no failures, just slow tests (test_oss_freshness.py). Recurring issue from prior fix cycles.

**Command output**:
```
...(truncated)...
ge_loads_without_oss_errors PASSED [ 81%]
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
tests/integration/test_oss_freshness.py::TestOssFreshness::test_stale_detection_after_commit
[0m
All tests passing before timeout — the test suite is slow but healthy. The timeout hit at `test_oss_freshness.py::TestOssFreshness::test_stale_detection_after_commit` (at ~82%). Let me check that test:
[0m✱ [0mGrep "test_stale_detection_after_commit"[90m in tests/integration · 1 match[0m
[0m
[0m$ [0mmkdir -p ai-dev/active/F-00073/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00073/reports/F-00073_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00073 --step S10 --reason "make allure-integration timed out after 300s at ~82% through integration suite. All visible tests passed before timeout — no failures, just slow tests (test_oss_freshness.py). Recurring issue from prior fix cycles."
Failed F-00073 step S10: make allure-integration timed out after 300s at ~82% through integration suite. All visible tests passed before timeout — no failures, just slow tests (test_oss_freshness.py). Recurring issue from prior fix cycles.
[0m
**FAIL** — `make allure-integration` timed out after 300s at ~82% through the suite.

All tests that ran before the timeout **passed** (no failures). The timeout hit during `test_oss_freshness.py::TestOssFreshness::test_stale_detection_after_commit`. This is a recurring infrastructure issue — the integration suite consistently exceeds the 5-minute gate budget. Report written to `ai-dev/active/F-00073/reports/F-00073_S10_QvGate_report.md`.

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
