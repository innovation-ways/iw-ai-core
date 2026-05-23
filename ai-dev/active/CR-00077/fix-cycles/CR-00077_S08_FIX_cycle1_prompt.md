# CR-00077 S08 QV Fix Cycle 1/3

Quality gate S08 for work item CR-00077 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  dashboard/routers/batches.py
  dashboard/templates/fragments/batch_items_rows.html
  dashboard/templates/fragments/batch_overlap_modal.html
  dashboard/templates/pages/project/batch_detail.html
  dashboard/static/styles.css
  tests/dashboard/test_batch_overlap_modal.py
  tests/unit/test_batch_overlap_grouping.py
  dashboard/routers/actions.py
  tests/dashboard/test_batch_held_indicator.py

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00077/ai-dev/active/CR-00077/CR-00077_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: lint failed: exit=2

**Unparseable output** (always surfaces):
  uv run python scripts/check_templates.py
  uv run ruff check .
  E501 Line too long (115 > 100)
     --> dashboard/routers/batches.py:200:101
      |
  198 |     # ordered deduplication so glob order matches event order).
  199 |     item_statuses: dict[str, ScopeStatus] = {}
  200 |     item_blocking_globs: dict[str, dict[str, list[str]]] = {}  # entity_id → blocking_id → ordered globs (no dupes)
      |                                                                                                     ^^^^^^^^^^^^^^^
  201 |     item_policy_allowed: dict[str, ScopeStatus] = {}  # entity_id → policy_allowed Status (held takes precedence)
  202 |     for ev in rows:
      |
  E501 Line too long (113 > 100)
     --> dashboard/routers/batches.py:201:101
      |
  199 |     item_statuses: dict[str, ScopeStatus] = {}
  200 |     item_blocking_globs: dict[str, dict[str, list[str]]] = {}  # entity_id → blocking_id → ordered globs (no dupes)
  201 |     item_policy_allowed: dict[str, ScopeStatus] = {}  # entity_id → policy_allowed Status (held takes precedence)
      |                                                                                                     ^^^^^^^^^^^^^
  202 |     for ev in rows:
  203 |         entity_id = ev.entity_id
      |
  Found 2 errors.
  make: *** [Makefile:27: lint] Error 1


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
