# CR-00066 S09 QV Fix Cycle 2/7

Quality gate S09 for work item CR-00066 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/db/models.py
  orch/db/migrations/versions/**
  orch/daemon/step_monitor.py
  dashboard/routers/items.py
  dashboard/templates/fragments/item_steps_table.html
  dashboard/static/styles.css
  tests/unit/test_step_monitor_token_poll.py
  tests/integration/test_context_tokens_migration.py
  ai-dev/active/CR-00066/**
  ai-dev/work/CR-00066/**

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00066/ai-dev/active/CR-00066/CR-00066_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
 50.0% reached. Total coverage: 63.29%
=========================== short test summary info ============================
FAILED tests/dashboard/test_item_overview_action_buttons.py::TestItemOverviewRenders::test_in_progress_step_renders_kill_button
FAILED tests/dashboard/test_item_overview_action_buttons.py::TestItemOverviewRenders::test_completed_step_renders_no_action_buttons
FAILED tests/dashboard/test_item_overview_action_buttons.py::TestItemOverviewRenders::test_failed_merge_renders_restart_merge_button
FAILED tests/dashboard/test_item_overview_action_buttons.py::TestItemOverviewRenders::test_needs_fix_step_renders_restart_and_skip
FAILED tests/dashboard/test_item_overview_action_buttons.py::TestItemOverviewRenders::test_failed_step_renders_restart_and_skip
FAILED tests/dashboard/test_item_overview_action_buttons.py::TestDbStaleDisablesButtons::test_kill_button_disabled_when_db_stale
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock
FAILED tests/dashboard/test_item_overview_awaiting_merge.py::TestAwaitingApprovalMergeButton::test_completed_merge_renders_no_action_buttons
FAILED tests/dashboard/test_item_overview_awaiting_merge.py::TestAwaitingApprovalMergeButton::test_merge_failed_shows_restart_and_abandon
FAILED tests/dashboard/test_item_overview_awaiting_merge.py::TestAwaitingApprovalMergeButton::test_awaiting_approval_does_not_render_abandon_merge
FAILED tests/dashboard/test_item_overview_awaiting_merge.py::TestAwaitingApprovalMergeButton::test_awaiting_approval_does_not_render_restart_merge
FAILED tests/dashboard/test_item_overview_awaiting_merge.py::TestAwaitingApprovalMergeButton::test_awaiting_approval_renders_merge_button
FAILED tests/dashboard/test_item_overview_awaiting_merge.py::TestAwaitingApprovalMergeButton::test_failed_merge_still_shows_restart_and_abandon
FAILED tests/dashboard/test_cascade_history.py::TestRunCountBadge::test_run_count_badge_absent_when_runs_eq_1
FAILED tests/dashboard/test_cascade_history.py::TestRunCountBadge::test_run_count_badge_htmx_endpoint_url
FAILED tests/dashboard/test_cascade_history.py::TestRunCountBadge::test_step_run_count_badge_shown_when_runs_gt_1
FAILED tests/dashboard/test_cascade_history.py::TestRunCountBadge::test_run_count_badge_absent_for_synthetic_steps
FAILED tests/dashboard/test_cascade_history.py::TestRunCountBadge::test_run_count_badge_has_aria_label
FAILED tests/dashboard/test_item_steps_table_render.py::TestPromptColumnRendering::test_synthetic_s00_row_renders_when_no_workflow_steps
FAILED tests/integration/test_n1_bounded_queries.py::TestItemDetailBoundedQueries::test_get_steps_query_count_bounded
= 21 failed, 2790 passed, 32 skipped, 3 xfailed, 3 xpassed, 149 warnings in 1068.44s (0:17:48) =
make: *** [Makefile:105: test-integration] Error 1
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
