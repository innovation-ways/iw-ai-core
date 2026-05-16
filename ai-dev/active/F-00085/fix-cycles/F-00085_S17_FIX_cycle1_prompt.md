# F-00085 S17 QV Fix Cycle 1/5

Quality gate S17 for work item F-00085 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00085/ai-dev/active/F-00085/F-00085_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: assertions failed: exit=2

**Gate report**:
```
# F-00085 S17 QvGate Report

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
tests/dashboard/test_auto_merge_routes.py:229: tautology: test_ac9_existing_routes_unaffected: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/integration/test_auto_merge_control_surface.py:141: tautology: test_invariant_9_config_updated_event_records_before_after: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/integration/test_auto_merge_observability.py:65: tautology: test_ac4_boundary_file_no_longer_on_main: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/test_auto_merge_config_resolution.py:100: no-assert: test_resolve_disabled_runtime_emits_auto_merge_config_invalid_once: function body contains no assertions
tests/unit/test_auto_merge_health.py:28: no-assert: test_probe_skipped_when_recent_event_exists: function body contains no assertions
tests/unit/test_auto_merge_health.py:83: no-assert: test_probe_skipped_when_phase_0: function body contains no assertions
tests/unit/test_auto_merge_health.py:118: tautology: test_probe_non_blocking_does_not_raise: every assert matches a tautological form (is not None / isinstance / len > 0)
make: *** [Makefile:63: test-assertions] Error 1
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
