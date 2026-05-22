# I-00102 S09 QV Fix Cycle 1/3

Quality gate S09 for work item I-00102 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/cli/item_commands.py
  orch/db/models.py
  orch/db/migrations/versions/**
  tests/integration/test_item_register_drift.py
  tests/unit/test_item_commands_digest.py
  ai-dev/active/I-00102/**
  ai-dev/work/I-00102/**
  tests/integration/daemon/test_phase2_apply_no_self_deadlock.py

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00102/ai-dev/active/I-00102/I-00102_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: lint failed: exit=2

**Unparseable output** (always surfaces):
  uv run python scripts/check_templates.py
  uv run ruff check .
  E501 Line too long (106 > 100)
    --> tests/integration/daemon/test_phase2_apply_no_self_deadlock.py:41:101
     |
  39 | _HEAD_REVISION = "aeb0e4106b55"  # add_manifest_digest_to_work_items (I-00102, current head)
  40 | _PREV_REVISION = (
  41 |     "891343247f66"  # cr00066_add_context_tokens_columns (stamped here; manifest_digest migration pending)
     |                                                                                                     ^^^^^^
  42 | )
     |
  Found 1 error.
  make: *** [Makefile:25: lint] Error 1


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
