# F-00086 S15 QV Fix Cycle 1/7

Quality gate S15 for work item F-00086 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/chat/__init__.py
  orch/chat/runtime_base.py
  orch/chat/opencode/**
  orch/chat/tab_service.py
  orch/chat/migration_helpers.py
  orch/db/models.py
  orch/db/migrations/versions/**
  dashboard/routers/chat.py
  dashboard/app.py
  dashboard/templates/chat_assistant/**
  dashboard/static/chat_assistant/**
  dashboard/static/styles.css
  tests/unit/chat/**
  tests/dashboard/test_chat_*.py
  tests/integration/test_chat_*.py
  ai-dev/active/F-00086/**
  ai-dev/archive/F-00086/**

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00086/ai-dev/active/F-00086/F-00086_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
tonVisibilityParametrisedBatch::test_batch_cancel_button_hidden_for_terminal_statuses[terminal_publishing]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_visible_for_cancellable_statuses[BatchStatus.published]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_hidden_for_terminal_statuses[terminal_completed]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_visible_for_cancellable_statuses[BatchStatus.completed]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_hidden_for_terminal_statuses[terminal_published]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_visible_for_cancellable_statuses[BatchStatus.publishing]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_hidden_for_terminal_statuses[terminal_completed_with_errors]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_visible_for_cancellable_statuses[BatchStatus.archived]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestBoundaryBatchCancelButton::test_cancel_button_hidden_on_terminal_batch[terminal_archived]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestBoundaryBatchCancelButton::test_cancel_button_hidden_on_terminal_batch[terminal_completed]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestBoundaryBatchCancelButton::test_cancel_button_hidden_on_terminal_batch[terminal_cancelled]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestBoundaryBatchCancelButton::test_cancel_button_hidden_on_terminal_batch[terminal_completed_with_errors]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedItem::test_item_cancel_button_hidden_for_non_cancellable_status[non_cancellable_cancelled]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedItem::test_item_cancel_button_hidden_for_non_cancellable_status[non_cancellable_draft]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedItem::test_item_cancel_button_hidden_for_non_cancellable_status[non_cancellable_completed]
FAILED tests/dashboard/test_cancel_confirm_dialog.py::TestItemCancelInActiveBatch::test_item_cancel_disabled_with_hint_when_in_active_batch
FAILED tests/dashboard/test_cancel_confirm_dialog.py::TestCancelBatchTerminalRefused::test_cancel_button_hidden_for_terminal_batch
= 25 failed, 2715 passed, 32 skipped, 4 xfailed, 2 xpassed, 149 warnings in 974.97s (0:16:14) =
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
