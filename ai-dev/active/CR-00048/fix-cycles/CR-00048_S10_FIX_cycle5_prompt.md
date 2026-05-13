# CR-00048 S10 QV Fix Cycle 5/5

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
ive_cleanup
ERROR tests/integration/test_evidences_lifecycle.py::TestApproveOversizeRollback::test_approve_oversize_keeps_status_draft_no_rows
ERROR tests/integration/test_evidences_lifecycle.py::TestStepDoneIngestsPostEvidences::test_step_done_implementation_does_not_ingest
ERROR tests/integration/test_evidences_lifecycle.py::TestStepDoneIngestsPostEvidences::test_step_done_browser_verification_ingests_post
ERROR tests/integration/test_evidences_lifecycle.py::TestApproveIngestsPreEvidences::test_approve_ingests_pre_2_files_png_and_yaml
ERROR tests/integration/test_f_00076_research_bypass.py::TestResearchBypass::test_research_with_identical_paths_as_feature_still_bypasses
ERROR tests/integration/test_f_00076_research_bypass.py::TestResearchBypass::test_research_item_bypasses_gate_with_overlapping_globs
ERROR tests/integration/test_f_00076_held_event_cadence.py::TestHeldEventCadence::test_no_new_event_after_blocker_merges
ERROR tests/integration/test_f_00076_held_event_cadence.py::TestHeldEventCadence::test_exactly_one_event_per_cycle_for_same_held_item
ERROR tests/integration/rag/test_chat_repo.py::TestChatRepo::test_get_or_create_conversation_creates_new
ERROR tests/integration/rag/test_chat_repo.py::TestChatRepo::test_get_conversation_strict_triple_filter
ERROR tests/integration/rag/test_chat_repo.py::TestChatRepo::test_get_or_create_conversation_returns_existing
ERROR tests/integration/rag/test_chat_repo.py::TestChatRepo::test_append_message_updates_last_active_at
ERROR tests/integration/rag/test_chat_repo.py::TestChatRepo::test_archive_conversation_cross_project_returns_none
ERROR tests/integration/rag/test_chat_repo.py::TestChatRepo::test_archive_conversation_idempotent
ERROR tests/integration/rag/test_chat_repo.py::TestChatRepo::test_list_messages_for_context_skips_summarized
ERROR tests/integration/rag/test_chat_repo.py::TestChatRepo::test_get_or_create_conversation_cross_session_returns_none
ERROR tests/integration/test_merge_queue_auto_merge_gate.py::test_auto_merge_true_completed_item_is_picked_by_merge_queue
ERROR tests/integration/test_merge_queue_auto_merge_gate.py::test_failed_item_bypasses_gate
ERROR tests/integration/test_merge_queue_auto_merge_gate.py::test_approve_merge_emits_daemon_event
ERROR tests/integration/test_merge_queue_auto_merge_gate.py::test_approve_merge_service_transitions_to_completed
ERROR tests/integration/test_merge_queue_auto_merge_gate.py::test_auto_merge_false_item_stays_at_awaiting_merge_approval
ERROR tests/integration/test_merge_queue_auto_merge_gate.py::test_approved_item_is_picked_by_merge_queue_next_tick
ERROR tests/integration/test_merge_queue_auto_merge_gate.py::test_awaiting_merge_approval_items_are_invisible_to_merge_queue
ERROR tests/integration/test_merge_queue_auto_merge_gate.py::test_executing_item_that_fails_stays_at_failed
152 failed, 1734 passed, 33 skipped, 3 xfailed, 660 warnings, 375 errors in 739.04s (0:12:19)
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


**ESCALATION**: This is the FINAL fix cycle (5/5). **PREFER honest escalation over a Hail-Mary fix that drifts from the design spec.** If you cannot resolve every issue while staying aligned with the design doc, document which issues remain and why — the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
