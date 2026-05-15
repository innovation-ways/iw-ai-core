# CR-00053 S09 QV Fix Cycle 3/3

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
  E501 Line too long (111 > 100)
     --> tests/dashboard/test_cancel_confirm_dialog.py:782:101
      |
  780 |         assert result.count('name="reason"') == 1, "Textarea must have name='reason' attribute once"
  781 |         # Non-cancel approve action URL must be preserved in the rendered output
  782 |         assert result.count("/api/batch/BATCH-001/approve") == 1, "Approve action URL must appear exactly once"
      |                                                                                                     ^^^^^^^^^^^
  783 |         # Danger=true in confirm_dialog produces a destructive-styled submit button
  784 |         assert "bg-destructive" in result, "Destructive button must have bg-destructive class"
      |
  E501 Line too long (105 > 100)
    --> tests/dashboard/test_confirm_dialog_form.py:77:101
     |
  75 |     # danger=True renders a non-empty form with all expected structural elements
  76 |     assert rendered.count("<form") == 1, "Exactly one form element must be rendered"
  77 |     assert rendered.count('hx-post="/api/item/X-1/cancel"') == 1, "Cancel htmx post URL must appear once"
     |                                                                                                     ^^^^^
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


**ESCALATION**: This is the FINAL fix cycle (3/3). **PREFER honest escalation over a Hail-Mary fix that drifts from the design spec.** If you cannot resolve every issue while staying aligned with the design doc, document which issues remain and why — the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
