# CR-00053 S09 QV Fix Cycle 2/3

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
  PT018 Assertion should be broken down into multiple parts
     --> tests/dashboard/test_cancel_confirm_dialog.py:780:9
      |
  778 |           # The form (textarea + checkbox) is always present in this template.
  779 |           # Assert the textarea element with its name attribute (not just substring match)
  780 | /         assert "<textarea" in result and 'name="reason"' in result, (
  781 | |             "Template must contain a textarea with name='reason'"
  782 | |         )
      | |_________^
  783 |           assert 'name="reason"' in result, "Textarea must have name='reason'"
  784 |           # Danger=true in confirm_dialog produces a destructive-styled submit button
      |
  help: Break down assertion into multiple parts
  PT018 Assertion should be broken down into multiple parts
    --> tests/dashboard/test_confirm_dialog_form.py:70:5
     |
  68 |     # Form fields must be present — assert on textarea element (complete tag with
  69 |     # attribute, not just the name substring) and checkbox label text (from form_html)
  70 |     assert '<textarea' in rendered and 'name="reason"' in rendered, "Textarea must be present in the form"
     |     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  71 |     assert "Also reset to draft</label>" in rendered, "Checkbox label must be present in the form"
  72 |     # Confirm button label must be present
     |
  help: Break down assertion into multiple parts
  E501 Line too long (106 > 100)
    --> tests/dashboard/test_confirm_dialog_form.py:70:101
     |
  68 |     # Form fields must be present — assert on textarea element (complete tag with
  69 |     # attribute, not just the name substring) and checkbox label text (from form_html)
  70 |     assert '<textarea' in rendered and 'name="reason"' in rendered, "Textarea must be present in the form"
     |                                                                                                     ^^^^^^
  71 |     assert "Also reset to draft</label>" in rendered, "Checkbox label must be present in the form"
  72 |     # Confirm button label must be present
     |
  Found 3 errors.
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
