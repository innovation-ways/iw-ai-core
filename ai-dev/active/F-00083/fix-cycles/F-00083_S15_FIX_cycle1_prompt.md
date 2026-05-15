# F-00083 S15 QV Fix Cycle 1/7

Quality gate S15 for work item F-00083 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00083/ai-dev/active/F-00083/F-00083_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
ses[BatchStatus.blocked]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_visible_for_cancellable_statuses[BatchStatus.archived]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_visible_for_cancellable_statuses[BatchStatus.cancelled]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_hidden_for_terminal_statuses[terminal_completed]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_hidden_for_terminal_statuses[terminal_completed_with_errors]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_hidden_for_terminal_statuses[terminal_publishing]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_hidden_for_terminal_statuses[terminal_published]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_hidden_for_terminal_statuses[terminal_archived]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestCancelButtonVisibilityParametrisedBatch::test_batch_cancel_button_hidden_for_terminal_statuses[terminal_cancelled]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestBoundaryBatchCancelButton::test_cancel_button_on_cancellable_batch_status[cancellable_planning]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestBoundaryBatchCancelButton::test_cancel_button_on_cancellable_batch_status[cancellable_approved]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestBoundaryBatchCancelButton::test_cancel_button_on_cancellable_batch_status[cancellable_executing]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestBoundaryBatchCancelButton::test_cancel_button_on_cancellable_batch_status[cancellable_paused]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestBoundaryBatchCancelButton::test_cancel_button_hidden_on_terminal_batch[terminal_completed]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestBoundaryBatchCancelButton::test_cancel_button_hidden_on_terminal_batch[terminal_completed_with_errors]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestBoundaryBatchCancelButton::test_cancel_button_hidden_on_terminal_batch[terminal_archived]
FAILED tests/dashboard/test_cancel_button_visibility.py::TestBoundaryBatchCancelButton::test_cancel_button_hidden_on_terminal_batch[terminal_cancelled]
FAILED tests/dashboard/test_cancel_confirm_dialog.py::TestCancelBatchTerminalRefused::test_cancel_button_hidden_for_terminal_batch
= 45 failed, 2371 passed, 33 skipped, 3 xfailed, 167 warnings in 659.32s (0:10:59) =
make: *** [Makefile:87: test-integration] Error 1
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
