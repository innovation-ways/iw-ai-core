# F-00084 S10 QV Fix Cycle 1/5

Quality gate S10 for work item F-00084 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00084/ai-dev/active/F-00084/F-00084_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: assertions failed: exit=2

**Gate report**:
```
# F-00084 S10 QvGate Report

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
tests/unit/test_auto_merge_config.py:181: tautology: test_load_refuselist_patterns_default: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/test_auto_merge_prompt.py:50: tautology: test_prompt_includes_work_item_header: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/test_auto_merge_prompt.py:61: tautology: test_prompt_includes_file_path: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/test_auto_merge_prompt.py:71: tautology: test_prompt_includes_three_way_content: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/test_auto_merge_prompt.py:117: tautology: test_prompt_includes_abstain_clause: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/test_auto_merge_prompt.py:245: tautology: test_prompt_contains_abstain_token: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/test_auto_merge_prompt.py:263: tautology: test_prompt_contains_work_item_info: every assert matches a tautological form (is not None / isinstance / len > 0)
tests/unit/test_auto_merge_prompt.py:282: tautology: test_prompt_contains_file_path: every assert matches a tautological form (is not None / isinstance / len > 0)
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
