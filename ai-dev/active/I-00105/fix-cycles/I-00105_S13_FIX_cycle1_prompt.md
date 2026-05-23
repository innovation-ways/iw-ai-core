# I-00105 S13 QV Fix Cycle 1/5

Quality gate S13 for work item I-00105 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/db/models.py
  orch/db/migrations/versions/**
  orch/chat/**
  orch/config.py
  dashboard/routers/items.py
  dashboard/routers/chat.py
  dashboard/templates/**
  dashboard/static/chat_assistant/**
  executor/**
  tests/**
  docs/IW_AI_Core_Daemon_Design.md

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00105/ai-dev/active/I-00105/I-00105_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: assertions failed: exit=2

**Gate report**:
```
# I-00105 S13 QvGate Report

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
tests/unit/executor/test_context_overflow.py:122: tautology: test_returns_dataclass_with_detected_boolean: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/executor/test_context_overflow.py:162: tautology: test_known_labels_present: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/executor/test_tool_output_cap.py:71: tautology: test_filename_contains_item_and_step: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/executor/test_tool_output_cap.py:180: tautology: test_over_cap_preview_contains_file_path: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/executor/test_tool_output_cap.py:193: tautology: test_over_cap_preview_contains_total_size: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/executor/test_tool_output_cap.py:297: tautology: test_returns_capresult_dataclass: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/executor/test_tool_output_cap.py:313: tautology: test_preview_is_string: every assert matches a tautological form (is not None / isinstance / len > 0)
make: *** [Makefile:68: test-assertions] Error 1
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
