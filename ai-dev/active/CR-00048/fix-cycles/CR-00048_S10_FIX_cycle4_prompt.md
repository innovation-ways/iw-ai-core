# CR-00048 S10 QV Fix Cycle 4/5

Quality gate S10 for work item CR-00048 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00048/ai-dev/active/CR-00048/CR-00048_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: diff-coverage failed: exit=2

**Gate report**:
```
...(truncated)...
_to_executing
ERROR tests/integration/test_batch_manager.py::TestBatchLifecycleFull::test_step_completion_launches_next_step
ERROR tests/integration/test_batch_manager.py::TestBatchLifecycleFull::test_self_assess_failure_does_not_block_item_completion
ERROR tests/integration/test_batch_manager.py::TestBatchLifecycleFull::test_all_merged_completes_batch
ERROR tests/integration/test_batch_manager.py::TestBatchLifecycleFull::test_pending_item_gets_launched
ERROR tests/integration/test_execution_report_dashboard_route.py::test_execution_report_page_contains_execution_markdown
ERROR tests/integration/test_execution_report_dashboard_route.py::test_execution_report_page_returns_200_for_known_item
ERROR tests/integration/test_execution_report_dashboard_route.py::test_execution_report_tab_html_contains_gantt_rows
ERROR tests/integration/test_execution_report_dashboard_route.py::test_execution_report_tab_html_contains_summary_card
ERROR tests/integration/test_execution_report_dashboard_route.py::test_execution_report_tab_returns_404_for_unknown_item
ERROR tests/integration/test_execution_report_dashboard_route.py::test_execution_report_tab_returns_200_for_known_item
ERROR tests/integration/test_execution_report_dashboard_route.py::test_execution_report_page_returns_404_for_unknown_item
ERROR tests/integration/test_execution_report_dashboard_route.py::test_existing_tabs_byte_identical
ERROR tests/integration/test_f_00076_scope_extraction_round_trip.py::test_declared_scope_source_is_declared
ERROR tests/integration/test_f_00076_scope_extraction_round_trip.py::test_research_item_keeps_none_source
ERROR tests/integration/test_f_00076_scope_extraction_round_trip.py::test_no_paths_anywhere_source_is_none
ERROR tests/integration/test_f_00076_scope_extraction_round_trip.py::test_declared_empty_paths_source_is_declared
ERROR tests/integration/test_f_00076_scope_extraction_round_trip.py::test_missing_section_with_file_paths_source_is_regex_fallback
ERROR tests/integration/test_merge_failure_does_not_cascade.py::TestMergeFailureDoesNotCascade::test_recoverable_merge_failure_does_not_cascade[BatchItemStatus.migration_rebase_failed]
ERROR tests/integration/test_merge_failure_does_not_cascade.py::TestMergeFailureDoesNotCascade::test_recoverable_merge_failure_does_not_cascade[BatchItemStatus.merge_failed]
ERROR tests/integration/test_merge_failure_does_not_cascade.py::TestMergeFailureDoesNotCascade::test_recoverable_merge_failure_does_not_cascade[BatchItemStatus.migration_invalid]
ERROR tests/integration/test_merge_failure_does_not_cascade.py::TestMergeFailureDoesNotCascade::test_no_batch_dependency_failed_event_on_recoverable_failure
ERROR tests/integration/test_merge_failure_does_not_cascade.py::TestMergeQueueMergeFailedWritesCorrectStatus::test_merge_queue_process_writes_merge_failed_on_merge_error
314 failed, 1386 passed, 33 skipped, 3 xfailed, 968 warnings, 561 errors in 861.52s (0:14:21)
make: *** [Makefile:134: diff-coverage] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make diff-coverage
```

After applying fixes, re-run this command to verify the issues are resolved.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Skim the section that covers this step's scope; quote-of-the-doc lives in this prompt when available.
2. **Diff your target file(s) against the spec** — list deviations explicitly before editing.
3. **Apply the minimum patch** to align code with the spec; the reported errors should resolve as a side effect of that alignment.
4. **If the errors disagree with the spec, the spec wins.** Note the disagreement in your output rather than silently following the errors.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
