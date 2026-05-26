# F-00089 S12 QV Fix Cycle 1/5

Quality gate S12 for work item F-00089 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  tests/integration/daemon_chaos/**
  Makefile
  .github/workflows/daemon-chaos.yml
  skills/iw-workflow/SKILL.md
  .claude/skills/iw-workflow/SKILL.md
  skills/iw-ai-core-testing/SKILL.md
  .claude/skills/iw-ai-core-testing/**
  docs/IW_AI_Core_Testing_Strategy.md
  docs/IW_AI_Core_Daemon_Design.md
  ai-dev/work/TESTS_ENHANCEMENT.md

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/F-00089/**
  ai-dev/archive/F-00089/**
  ai-dev/work/F-00089/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00089/ai-dev/active/F-00089/F-00089_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: assertions failed: exit=2

**Gate report**:
```
# F-00089 S12 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | assertions      |
| Command      | `make test-assertions` |
| Exit code    | 2             |
| Result       | FAIL         |
| Duration (s) | 1       |

## Output (tail)

```
tests/integration/daemon_chaos/test_migration_rebase_failure.py:152: tautology: test_migration_rebase_failure_is_detected: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/integration/daemon_chaos/test_migration_rebase_failure.py:186: no-assert: test_no_alembic_revision_skips_scenario: function body contains no assertions
tests/integration/daemon_chaos/test_squash_merge_conflict.py:146: tautology: test_squash_merge_conflict_returns_recognised_error: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/integration/daemon_chaos/test_squash_merge_conflict.py:217: no-assert: test_squash_merge_conflict_empty_main_boundary: function body contains no assertions
make: *** [Makefile:70: test-assertions] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make test-assertions
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
5. **Post-edit cross-gate check (MANDATORY before exit).** When the
   failing gate is NOT lint/format, your edits may still introduce a
   new ruff violation that the next review run trips on. Before exiting,
   run `make format-check` and `make lint` and resolve any NEW violation
   your edits introduced (`uv run ruff format <file>` for format issues;
   targeted edit for lint). Diagnosed 2026-05-25 from CR-00082 S04's
   ping-pong between fix cycles where each agent re-broke the gate the
   previous one fixed.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
