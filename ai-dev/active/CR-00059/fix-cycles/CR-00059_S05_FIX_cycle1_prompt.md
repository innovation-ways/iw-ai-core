# CR-00059 S05 QV Fix Cycle 1/5

Quality gate S05 for work item CR-00059 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  pyproject.toml
  uv.lock
  Makefile
  docs/IW_AI_Core_Testing_Strategy.md
  ai-dev/work/TESTS_ENHANCEMENT.md
  tests/unit/test_mutmut_setup.py

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00059/ai-dev/active/CR-00059/CR-00059_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: assertions failed: exit=2

**Gate report**:
```
# CR-00059 S05 QvGate Report

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
uv run python scripts/check_test_assertions.py --baseline tests/assertion_free_baseline.txt tests/
tests/dashboard/test_chat_panel_event_protocol.py:71: tautology: test_chat_js_reads_properties_delta_for_streaming_text: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/dashboard/test_chat_panel_event_protocol.py:86: tautology: test_chat_js_history_reads_info_and_parts: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/dashboard/test_chat_panel_event_protocol.py:106: tautology: test_chat_js_preserves_session_storage_key: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/dashboard/test_chat_panel_event_protocol.py:119: tautology: test_chat_js_passes_last_event_id_on_reconnect: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/dashboard/test_chat_panel_event_protocol.py:133: tautology: test_chat_js_listens_for_session_idle: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/dashboard/test_chat_panel_event_protocol.py:142: tautology: test_chat_js_distinguishes_properties_from_data: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/dashboard/test_chat_panel_event_protocol.py:169: tautology: test_starter_listener_set_would_have_failed_protocol_check: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/test_auto_merge_health.py:68: no-assert: test_probe_invokes_lib_script_with_expected_argv_shape: function body contains no assertions
make: *** [Makefile:64: test-assertions] Error 1
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
