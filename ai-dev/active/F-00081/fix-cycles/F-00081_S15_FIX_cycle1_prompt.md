# F-00081 S15 QV Fix Cycle 1/7

Quality gate S15 for work item F-00081 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00081/ai-dev/active/F-00081/F-00081_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
p::test_self_assess_failure_does_not_block_merge
ERROR tests/integration/test_batch_manager_self_assess.py::TestSelfAssessSoftStep::test_self_assess_failed_renders_with_partial_data
ERROR tests/integration/test_batch_manager_self_assess.py::TestImplementationFailureBlocksMerge::test_implementation_failure_does_not_advance_to_completed
ERROR tests/integration/test_batch_manager_self_assess.py::TestImplementationFailureBlocksMerge::test_self_assess_timeout_is_soft
ERROR tests/integration/test_browser_verification_flow.py::test_launch_step_env_up_failure_marks_step_failed
ERROR tests/integration/test_browser_verification_flow.py::test_launch_step_env_up_success_launches_agent_with_env
ERROR tests/integration/test_browser_verification_flow.py::test_launch_step_non_browser_step_no_hooks_called
ERROR tests/integration/test_f_00076_cross_project_no_block.py::TestCrossProjectNoBlock::test_identical_paths_in_different_projects_both_launch
ERROR tests/integration/test_f_00076_e2e.py::TestE2EScopeGate::test_overlapping_features_different_batches_held_then_releases
ERROR tests/integration/test_f_00076_e2e.py::TestE2EScopeGate::test_only_one_item_launches_per_project_per_cycle_when_overlap
ERROR tests/integration/test_f_00076_held_event_cadence.py::TestHeldEventCadence::test_exactly_one_event_per_cycle_for_same_held_item
ERROR tests/integration/test_f_00076_held_event_cadence.py::TestHeldEventCadence::test_no_new_event_after_blocker_merges
ERROR tests/integration/test_f_00076_research_bypass.py::TestResearchBypass::test_research_item_bypasses_gate_with_overlapping_globs
ERROR tests/integration/test_f_00076_research_bypass.py::TestResearchBypass::test_research_with_identical_paths_as_feature_still_bypasses
ERROR tests/integration/test_f_00076_test_globs_ignored.py::TestTestGlobsIgnored::test_overlap_only_on_test_glob_both_launch
ERROR tests/integration/test_f_00076_test_globs_ignored.py::TestTestGlobsIgnored::test_conftest_overlap_ignored
ERROR tests/integration/test_merge_failure_does_not_cascade.py::TestMergeFailureDoesNotCascade::test_recoverable_merge_failure_does_not_cascade[BatchItemStatus.merge_failed]
ERROR tests/integration/test_merge_failure_does_not_cascade.py::TestMergeFailureDoesNotCascade::test_recoverable_merge_failure_does_not_cascade[BatchItemStatus.migration_invalid]
ERROR tests/integration/test_merge_failure_does_not_cascade.py::TestMergeFailureDoesNotCascade::test_recoverable_merge_failure_does_not_cascade[BatchItemStatus.migration_rebase_failed]
ERROR tests/integration/test_merge_failure_does_not_cascade.py::TestMergeFailureDoesNotCascade::test_no_batch_dependency_failed_event_on_recoverable_failure
ERROR tests/integration/test_merge_failure_does_not_cascade.py::TestMergeQueueMergeFailedWritesCorrectStatus::test_merge_queue_process_writes_merge_failed_on_merge_error
= 37 failed, 2054 passed, 32 skipped, 3 xfailed, 164 warnings, 40 errors in 527.78s (0:08:47) =
make: *** [Makefile:55: test-integration] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make test-integration
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
