# CR-00078 S13 QV Fix Cycle 1/3

Quality gate S13 for work item CR-00078 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/db/models.py
  orch/db/migrations/versions/**
  orch/daemon/batch_manager.py
  orch/daemon/overlap_ignore.py
  orch/daemon/scope_overlap.py
  dashboard/routers/batches.py
  dashboard/routers/actions.py
  dashboard/templates/fragments/batch_overlap_modal.html
  dashboard/static/styles.css
  tests/unit/test_batch_overlap_ignore.py
  tests/unit/test_daemon_overlap_filter.py
  tests/integration/test_batch_overlap_ignore_flow.py
  tests/dashboard/test_batch_overlap_ignore_endpoints.py
  tests/dashboard/test_batch_overlap_modal.py
  tests/integration/daemon/test_phase2_apply_no_self_deadlock.py
  tests/dashboard/test_route_contract_sweep.py

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00078/ai-dev/active/CR-00078/CR-00078_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: lint failed: exit=2

**Unparseable output** (always surfaces):
  uv run python scripts/check_templates.py
  uv run ruff check .
  E501 Line too long (143 > 100)
     --> tests/dashboard/test_route_contract_sweep.py:122:101
      |
  120 | …ctions/{section_name}",  # diff section name
  121 | …id}",  # auto-merge event id not seeded
  122 | …{held_item_id}",  # overlap modal GET (CR-00077; /ignore and /ignore-all are POST only)
      |                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  123 | …phase}/{filename}",  # evidence file path
  124 | …t/{step_db_id}/{run_number}",  # log coords
      |
  E501 Line too long (108 > 100)
    --> tests/integration/daemon/test_phase2_apply_no_self_deadlock.py:10:101
     |
   8 | leaving two migrations pending:
   9 | - 3a3dfec7bfbd (CR-00078 add batch_overlap_ignore) — adds the batch_overlap_ignore table
  10 | - aeb0e4106b55 (add_manifest_digest_to_work_items, I-00102) — adds the manifest_digest column to work_items.
     |                                                                                                     ^^^^^^^^
  11 |
  12 | This migration does NOT ALTER TABLE batch_items, so the AccessShareLock on
     |
  E501 Line too long (108 > 100)
    --> tests/integration/daemon/test_phase2_apply_no_self_deadlock.py:41:101
     |
  39 | _HEAD_REVISION = "3a3dfec7bfbd"  # CR-00078 add batch_overlap_ignore (current head)
  40 | _PREV_REVISION = (
  41 |     "891343247f66"  # cr00066_add_context_tokens_columns (stamped here; CR-00078 + digest migration pending)
     |                                                                                                     ^^^^^^^^
  42 | )
     |
  Found 3 errors.
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
