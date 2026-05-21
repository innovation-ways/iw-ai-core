# CR-00066 S09 QV Fix Cycle 1/7

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
e_steps_returns_info_toast
FAILED tests/dashboard/test_runtime_override_response.py::test_per_step_clear_override_returns_fragment_and_toast_trigger
FAILED tests/integration/test_dashboard_pages.py::test_item_detail_returns_200
FAILED tests/integration/test_dashboard_pages.py::test_item_reports_tab_shows_step_reports
FAILED tests/integration/test_dashboard_pages.py::test_item_detail_shows_batch_reference
FAILED tests/integration/test_dashboard_pages.py::test_item_overview_tab_returns_html
FAILED tests/integration/test_dashboard_pages.py::test_item_reports_tab_no_reports
FAILED tests/integration/test_dashboard_pages.py::test_item_detail_has_sse_script
FAILED tests/integration/test_context_tokens_migration.py::TestContextTokensMigration::test_migration_downgrade_removes_columns
FAILED tests/integration/test_pages_lazy_libs.py::TestPagesLazyLibs::test_item_detail_has_mermaid
FAILED tests/dashboard/test_item_overview_awaiting_merge.py::TestAwaitingApprovalMergeButton::test_merge_failed_shows_restart_and_abandon
FAILED tests/dashboard/test_item_overview_awaiting_merge.py::TestAwaitingApprovalMergeButton::test_failed_merge_still_shows_restart_and_abandon
FAILED tests/dashboard/test_item_overview_awaiting_merge.py::TestAwaitingApprovalMergeButton::test_awaiting_approval_does_not_render_restart_merge
FAILED tests/dashboard/test_item_overview_awaiting_merge.py::TestAwaitingApprovalMergeButton::test_awaiting_approval_renders_merge_button
FAILED tests/dashboard/test_item_overview_awaiting_merge.py::TestAwaitingApprovalMergeButton::test_completed_merge_renders_no_action_buttons
FAILED tests/dashboard/test_item_overview_awaiting_merge.py::TestAwaitingApprovalMergeButton::test_awaiting_approval_does_not_render_abandon_merge
FAILED tests/dashboard/test_cancel_confirm_dialog.py::TestItemCancelInActiveBatch::test_item_cancel_disabled_with_hint_when_in_active_batch
FAILED tests/dashboard/test_runtime_overrides_api.py::TestPatchStepRuntimeOverride::test_clears_step_override
FAILED tests/dashboard/test_runtime_overrides_api.py::TestPatchStepRuntimeOverride::test_emits_daemon_event_with_step_scope
FAILED tests/dashboard/test_runtime_overrides_api.py::TestPatchStepRuntimeOverride::test_sets_step_override
FAILED tests/dashboard/test_runtime_overrides_api.py::TestPatchBulkRuntimeOverride::test_bulk_skips_non_editable_steps
FAILED tests/dashboard/test_runtime_overrides_api.py::TestPatchBulkRuntimeOverride::test_bulk_emits_single_event
FAILED tests/dashboard/test_runtime_overrides_api.py::TestPatchBulkRuntimeOverride::test_bulk_sets_all_editable_steps
FAILED tests/dashboard/test_runtime_overrides_api.py::TestPatchBulkRuntimeOverride::test_bulk_zero_editable_steps_emits_no_event
FAILED tests/dashboard/test_runtime_overrides_api.py::TestPatchBulkRuntimeOverride::test_bulk_clears_all_editable_steps
= 104 failed, 2707 passed, 32 skipped, 4 xfailed, 2 xpassed, 149 warnings in 1097.91s (0:18:17) =
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
