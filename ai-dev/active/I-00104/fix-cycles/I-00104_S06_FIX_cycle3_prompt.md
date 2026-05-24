# I-00104 S06 QV Fix Cycle 3/3

Quality gate S06 for work item I-00104 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/batch_planner.py
  dashboard/routers/actions.py
  tests/unit/test_batch_planner_overlap.py
  tests/dashboard/test_batch_plan_max_parallel.py

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00104/ai-dev/active/I-00104/I-00104_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: lint failed: exit=2

**Unparseable output** (always surfaces):
  uv run python scripts/check_templates.py
  uv run ruff check .
  N806 Variable `CANCEL_BTN_REF` in function should be lowercase
    --> tests/e2e/test_journey_htmx_fragments.py:67:5
     |
  65 |     # reads a stale yml file, causing the dynamic ref to be empty, which
  66 |     # silently no-ops the click).
  67 |     CANCEL_BTN_REF = "e107"
     |     ^^^^^^^^^^^^^^
  68 |
  69 |     import time as _time
     |
  T201 `print` found
     --> tests/e2e/test_journey_htmx_fragments.py:126:9
      |
  124 |         import sys as _sys
  125 |
  126 |         print(
      |         ^^^^^
  127 |             f"NOTE: snap_before={len(snap_before)} == snap_after={len(snap_after)} "
  128 |             "(snapshot read race — dialog_inner confirms HTMX swap succeeded).",
      |
  help: Remove `print`
  Found 2 errors.
  No fixes available (1 hidden fix can be enabled with the `--unsafe-fixes` option).
  make: *** [Makefile:28: lint] Error 1


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
