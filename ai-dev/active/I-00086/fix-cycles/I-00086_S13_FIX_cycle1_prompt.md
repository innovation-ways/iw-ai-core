# I-00086 S13 QV Fix Cycle 1/7

Quality gate S13 for work item I-00086 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00086/ai-dev/active/I-00086/I-00086_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
153, 170-187, 193-199, 213-257, 270-279, 301-313, 318-345, 350-380, 389-433
orch/staleness/git_lookup.py                  58     45     16      0    18%   57-95, 121-180
orch/staleness/service.py                     94     63     24      0    26%   41-43, 115-124, 132-212, 240-289
orch/test_runner.py                          360    318     70      2    10%   43-224, 238-452, 460-485, 495-526, 540-548, 550, 563-570, 576-582, 587-594, 608-621, 626-632, 640-641, 657-679, 691-700
orch/utils/log_capture.py                     33     20      8      1    34%   36-62
--------------------------------------------------------------------------------------
TOTAL                                      22962   7960   6470    950    61%

28 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
Required test coverage of 50.0% reached. Total coverage: 61.40%
=========================== short test summary info ============================
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock
FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock
FAILED tests/integration/test_agent_runtime_options.py::TestAgentRuntimeOptionsTable::test_seed_rows_present
FAILED tests/integration/test_agent_runtime_options.py::TestAgentRuntimeOptionsTable::test_unique_constraint_on_cli_tool_model
FAILED tests/integration/test_agent_runtime_options.py::TestAgentRuntimeOptionsTable::test_can_disable_non_default_row
FAILED tests/integration/test_f00081_audit.py::TestAuditSingleStepPatch::test_single_step_override_emits_correct_event_shape
FAILED tests/integration/test_f00081_audit.py::TestAuditSingleStepPatch::test_clear_step_override_emits_event
FAILED tests/integration/test_f00081_audit.py::TestAuditBulkPatch::test_bulk_five_steps_emits_one_event_with_5_step_ids
FAILED tests/integration/test_f00081_audit.py::TestAuditBulkPatch::test_bulk_event_old_option_id_reflects_prior_state
FAILED tests/integration/test_f00081_audit.py::TestAuditBulkPatch::test_bulk_with_mixed_editable_non_editable_emits_event_with_only_editable_ids
FAILED tests/integration/test_f00081_boundaries.py::TestBoundaryBulkZeroEditable::test_bulk_zero_editable_returns_204_and_no_event
FAILED tests/integration/test_f00081_boundaries.py::TestBoundaryStepRace::test_bulk_skips_step_that_becomes_non_editable
FAILED tests/integration/test_f00081_invariants.py::TestInvariantOneEventPerCall::test_bulk_emits_single_event
FAILED tests/integration/test_f00081_invariants.py::TestInvariantOneEventPerCall::test_zero_editable_steps_emits_zero_events
= 14 failed, 2414 passed, 33 skipped, 3 xfailed, 164 warnings in 678.42s (0:11:18) =
make: *** [Makefile:193: allure-integration] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make allure-integration
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
