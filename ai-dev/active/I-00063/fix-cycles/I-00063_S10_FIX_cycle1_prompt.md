# I-00063 S10 QV Fix Cycle 1/5

Quality gate S10 for work item I-00063 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00063/ai-dev/active/I-00063/I-00063_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
ergeInfoConflictFiles::test_clean_rebase_no_conflicts_conflict_files_empty
FAILED tests/integration/daemon/test_merge_info_conflict_files.py::TestMergeInfoConflictFiles::test_multiple_conflict_files_captured
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_assert_no_self_blockers_raises_when_caller_holds_share_lock
FAILED tests/integration/dashboard/test_F00077_no_regressions.py::TestAC9NoRegressions::test_module_context_emits_expected_event_types
FAILED tests/integration/dashboard/test_F00077_no_regressions.py::TestAC9NoRegressions::test_diagram_command_emits_phase_and_diagram_events
FAILED tests/integration/dashboard/test_F00077_no_regressions.py::TestAC9NoRegressions::test_findusages_command_emits_phase
FAILED tests/integration/dashboard/test_F00077_no_regressions.py::TestAC9NoRegressions::test_error_event_still_emitted_on_failure
FAILED tests/integration/dashboard/test_F00077_no_regressions.py::TestAC9NoRegressions::test_meta_event_always_first
FAILED tests/integration/dashboard/test_F00077_stream_disconnect.py::TestStreamInterruption::test_interrupted_stream_persists_partial_with_error_flag
FAILED tests/integration/dashboard/test_F00077_stream_disconnect.py::TestStreamInterruption::test_partial_message_excluded_from_subsequent_history
FAILED tests/integration/dashboard/test_F00077_stream_disconnect.py::TestStreamInterruption::test_complete_messages_preserved_after_error
FAILED tests/integration/db/test_safe_migrate_self_blocker.py::test_assert_no_self_blockers_raises_when_same_process_holds_blocking_lock
FAILED tests/integration/db/test_safe_migrate_self_blocker.py::test_lock_timeout_env_var_honored
FAILED tests/integration/db/test_safe_migrate_self_blocker.py::test_pending_migration_log_written_on_self_blocker_failure
FAILED tests/integration/db/test_safe_migrate_self_blocker.py::test_pending_migration_log_written_on_lock_timeout_failure
FAILED tests/integration/db/test_safe_migrate_self_blocker.py::test_rollback_triggered_after_apply_failure
FAILED tests/integration/rag/test_F00077_multi_turn_e2e.py::TestF00077MultiTurnE2E::test_first_turn_creates_conversation_and_emits_meta
FAILED tests/integration/rag/test_F00077_multi_turn_e2e.py::TestF00077MultiTurnE2E::test_both_turns_persisted_and_streamed
FAILED tests/integration/rag/test_F00077_multi_turn_e2e.py::TestF00077MultiTurnE2E::test_ac1_name_persists_across_turns
FAILED tests/integration/test_batch_manager.py::TestMergeQueueIntegration::test_merge_queue_oldest_first
FAILED tests/integration/test_code_qa_no_regression.py::test_code_only_token_and_done_only
FAILED tests/integration/test_code_qa_no_regression.py::test_code_only_preserves_existing_sse_shape
= 24 failed, 1742 passed, 22 skipped, 1 xfailed, 162 warnings in 483.33s (0:08:03) =
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
