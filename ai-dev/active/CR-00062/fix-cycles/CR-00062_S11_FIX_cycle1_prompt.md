# CR-00062 S11 QV Fix Cycle 1/5

Quality gate S11 for work item CR-00062 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  executor/step_executor.sh
  executor/step_executor_lib.sh
  orch/daemon/batch_manager.py
  orch/daemon/fix_cycle.py
  orch/daemon/doc_job_poller.py
  orch/doc_service.py
  orch/daemon/project_registry.py
  orch/db/models.py
  orch/db/migrations/versions/**
  orch/skills/sync_agents.py
  orch/cli/skills_commands.py
  agents/pi/**
  tests/unit/**
  tests/integration/**

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00062/ai-dev/active/CR-00062/CR-00062_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: quality failed: exit=2

**Gate report**:
```
# CR-00062 S11 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | quality      |
| Command      | `make quality` |
| Exit code    | 2             |
| Result       | FAIL         |
| Duration (s) | 2       |

## Output (tail)

```
uv run python scripts/check_templates.py
uv run ruff check .
All checks passed!
uv run ruff format --check .
776 files already formatted
uv run mypy orch/ dashboard/
Success: no issues found in 257 source files
tests/unit/daemon/test_scope_overlap.py:127: tautology: test_mixed_test_and_prod_globs: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/test_auto_merge_aggregator.py:315: tautology: test_list_recent_events_include_non_auto_merge_shows_everything: every assert matches a tautological form (is not None / isinstance / len > 0)
make: *** [Makefile:66: test-assertions] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make quality
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
