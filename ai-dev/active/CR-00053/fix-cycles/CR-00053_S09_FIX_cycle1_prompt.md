# CR-00053 S09 QV Fix Cycle 1/3

Quality gate S09 for work item CR-00053 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00053/ai-dev/active/CR-00053/CR-00053_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: lint failed: exit=2

**Unparseable output** (always surfaces):
  uv run python scripts/check_templates.py
  uv run ruff check .
  E501 Line too long (103 > 100)
     --> tests/dashboard/test_cancel_button_visibility.py:519:101
      |
  518 |         assert cancel_batch_node is not None, "cancel_batch handler not found in actions.py"
  519 |         assert cancel_batch_node.name == "cancel_batch", "found node must be the cancel_batch function"
      |                                                                                                     ^^^
  520 |
  521 |         # Scan for direct status enum assignments like BatchStatus.X = ... or
      |
  E501 Line too long (116 > 100)
     --> tests/dashboard/test_confirm_dialog_form.py:130:101
      |
  128 |     assert hx_get_start != -1, "Cancel button must have hx-get attribute"
  129 |     hx_get_value = rendered[hx_get_start : rendered.find('"', hx_get_start + 9)]
  130 |     assert "confirm-batch/cancel/BATCH-1" in hx_get_value, "Cancel button hx-get must target confirm-batch endpoint"
      |                                                                                                     ^^^^^^^^^^^^^^^^
      |
  Found 2 errors.
  make: *** [Makefile:22: lint] Error 1


## Gate Command

The quality gate that failed runs:
```bash
make lint
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
