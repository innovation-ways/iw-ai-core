# F-00081 S15 QV Fix Cycle 3/7

Quality gate S15 for work item F-00081 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00081/ai-dev/active/F-00081/F-00081_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
0081_cascade.py::TestCascadeItemOverride::test_item_override_resolves_to_specified_pair
ERROR tests/integration/test_f00081_cascade.py::TestCascadeItemOverride::test_command_uses_claude_with_model
ERROR tests/integration/test_f00081_cascade.py::TestCascadeItemOverride::test_step_run_records_item_override_id
ERROR tests/integration/test_f00081_cascade.py::TestCascadeStepBeatsItem::test_step_override_wins
ERROR tests/integration/test_f00081_cascade.py::TestCascadeStepBeatsItem::test_item_override_used_when_step_has_none
ERROR tests/integration/test_f00081_cascade.py::TestCascadeMidFlight::test_running_step_unaffected_by_item_override_change
ERROR tests/integration/test_f00081_cascade.py::TestCascadeMidFlight::test_next_pending_step_picks_up_new_override
ERROR tests/integration/test_f00081_cascade.py::TestCascadeMidFlight::test_resolve_runtime_called_after_item_mutation_still_sees_new_value
ERROR tests/integration/test_f00081_invariants.py::TestInvariantOneDefault::test_exactly_one_default_row_exists
ERROR tests/integration/test_f00081_invariants.py::TestInvariantOneDefault::test_attempting_second_default_row_raises_integrity_error
ERROR tests/integration/test_f00081_invariants.py::TestInvariantOneDefault::test_default_row_cannot_be_disabled
ERROR tests/integration/test_f00081_invariants.py::TestInvariantOneDefault::test_default_row_remains_one_after_disabling_non_default
ERROR tests/integration/test_f00081_invariants.py::TestInvariantStepRunOptionIdNonNull::test_step_run_via_resolve_has_non_null_option_id
ERROR tests/integration/test_f00081_invariants.py::TestInvariantStepRunOptionIdNonNull::test_step_run_with_item_override_has_item_override_id
ERROR tests/integration/test_f00081_invariants.py::TestInvariantStepRunOptionIdNonNull::test_step_run_with_step_override_has_step_override_id
ERROR tests/integration/test_f00081_invariants.py::TestInvariantCommandHasModelFlag::test_opencode_command_contains_model_flag
ERROR tests/integration/test_f00081_invariants.py::TestInvariantCommandHasModelFlag::test_claude_command_contains_model_flag
ERROR tests/integration/test_f00081_invariants.py::TestInvariantCommandHasModelFlag::test_all_catalogue_options_produce_model_flag
ERROR tests/integration/test_f00081_invariants.py::TestInvariantOneEventPerCall::test_bulk_emits_single_event
ERROR tests/integration/test_f00081_invariants.py::TestInvariantOneEventPerCall::test_single_step_patch_emits_one_event
ERROR tests/integration/test_f00081_invariants.py::TestInvariantOneEventPerCall::test_zero_editable_steps_emits_zero_events
ERROR tests/integration/test_f00081_invariants.py::TestInvariantStepRunsAppendOnly::test_changing_item_override_does_not_touch_step_runs
ERROR tests/integration/test_f00081_invariants.py::TestInvariantStepRunsAppendOnly::test_changing_step_override_does_not_touch_step_runs
= 10 failed, 2057 passed, 32 skipped, 3 xfailed, 206 warnings, 64 errors in 564.90s (0:09:24) =
make: *** [Makefile:55: test-integration] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make test-integration
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
