# I-00111 S07 QV Fix Cycle 1/5

Quality gate S07 for work item I-00111 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  dashboard/routers/**
  dashboard/app.py
  orch/**
  tests/dashboard/test_schemathesis_contract.py
  tests/dashboard/test_openapi_schema.py

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00111/ai-dev/active/I-00111/I-00111_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: assertions failed: exit=2

**Gate report**:
```
# I-00111 S07 QvGate Report

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
tests/dashboard/test_keep_alive_slot_overflow.py:75: tautology: test_delete_slot_at_bigint_max_does_not_500: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/dashboard/test_keep_alive_slot_overflow.py:84: tautology: test_toggle_slot_at_bigint_max_does_not_500: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/daemon/test_daemon_config_reload.py:166: tautology: test_reload_rebuilds_manager_on_enabled_toggle: every assert matches a tautological form (is not None / isinstance / len > 0)
make: *** [Makefile:69: test-assertions] Error 1
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


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
