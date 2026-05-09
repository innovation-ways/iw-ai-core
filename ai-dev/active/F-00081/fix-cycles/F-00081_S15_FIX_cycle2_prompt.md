# F-00081 S15 QV Fix Cycle 2/7

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
les::test_clean_rebase_no_conflicts_conflict_files_empty
FAILED tests/integration/daemon/test_merge_info_conflict_files.py::TestMergeInfoConflictFiles::test_rebase_failure_with_conflict_files_still_captured
FAILED tests/integration/daemon/test_merge_info_conflict_files.py::TestMergeInfoConflictFiles::test_multiple_conflict_files_captured
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock
FAILED tests/integration/test_batch_manager.py::TestBatchLifecycleFull::test_pending_item_gets_launched
FAILED tests/integration/test_batch_manager.py::TestBatchLifecycleFull::test_step_completion_launches_next_step
FAILED tests/integration/test_browser_verification_flow.py::test_launch_step_env_up_failure_marks_step_failed
FAILED tests/integration/test_browser_verification_flow.py::test_launch_step_env_up_success_launches_agent_with_env
FAILED tests/integration/test_browser_verification_flow.py::test_launch_step_non_browser_step_no_hooks_called
FAILED tests/integration/test_fix_cycle.py::test_attempt_fix_cycle_creates_record
FAILED tests/integration/test_fix_cycle.py::test_attempt_fix_cycle_increments_cycle_number
FAILED tests/integration/test_fix_cycle_cascade_replay.py::test_failed_fix_cycle_does_not_cascade
ERROR tests/integration/daemon/test_batch_manager_scope_gate.py::TestBatchManagerScopeGate::test_overlapping_features_different_batches_second_held
ERROR tests/integration/daemon/test_batch_manager_scope_gate.py::TestBatchManagerScopeGate::test_research_item_bypasses_gate
ERROR tests/integration/daemon/test_batch_manager_scope_gate.py::TestBatchManagerScopeGate::test_merged_item_not_in_flight_candidate_launches
ERROR tests/integration/daemon/test_batch_manager_scope_gate.py::TestBatchManagerScopeGate::test_setup_failed_not_in_flight_candidate_launches
ERROR tests/integration/daemon/test_batch_manager_scope_gate.py::TestBatchManagerScopeGate::test_held_item_resumes_after_blocker_merges
ERROR tests/integration/daemon/test_batch_manager_scope_gate.py::TestBatchManagerScopeGate::test_two_pending_same_group_overlap_only_one_launches
ERROR tests/integration/test_abandon_merge_triggers_cascade.py::TestAbandonMergeTriggersCascade::test_abandon_merge_flips_to_failed_then_cascade_fires[BatchItemStatus.merge_failed]
ERROR tests/integration/test_abandon_merge_triggers_cascade.py::TestAbandonMergeTriggersCascade::test_abandon_merge_flips_to_failed_then_cascade_fires[BatchItemStatus.migration_invalid]
ERROR tests/integration/test_abandon_merge_triggers_cascade.py::TestAbandonMergeTriggersCascade::test_abandon_merge_flips_to_failed_then_cascade_fires[BatchItemStatus.migration_rebase_failed]
= 16 failed, 2106 passed, 32 skipped, 3 xfailed, 164 warnings, 9 errors in 537.64s (0:08:57) =
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
