# I-00082_S05_CodeReview_Final_prompt

**Work Item**: I-00082 — Fix-cycle agent has no allowed_paths enforcement
**Step**: S05
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/I-00082/I-00082_Issue_Design.md`
- All S01..S04 reports under `ai-dev/work/I-00082/reports/`
- The full diff: `git diff origin/main...HEAD` plus `git diff` for unstaged.

## Output Files

- `ai-dev/work/I-00082/reports/I-00082_S05_CodeReviewFinal_report.md`

## Cross-Agent Final Review

### Independently re-verify

- `uv run pytest tests/integration/test_fix_cycle_scope_enforcement.py -v` passes locally. Do **NOT** run `make test-integration` or `make test-unit` — those are the S10/S11 QV gates and have their own budgets.
- `git diff --stat` shows only `orch/daemon/fix_cycle.py` and the new test file. ANY other file in the diff is scope creep — flag CRITICAL.

### Confirm

- Every AC in the design doc has at least one passing assertion (the file
  combines S01's AC1 reproduction test with S03's AC3 and AC4 additions
  for 3 tests total covering all 4 ACs).
- The cycle outcome uses the **existing** `FixStatus.escalated` enum
  value from `orch/db/models.py:165` — there is no new string outcome
  like `escalate-to-operator`. Grep the codebase to confirm no new
  outcome value snuck in.
- A `DaemonEvent` of type `scope_violation_escalation` is emitted on
  violation, mirroring the existing `handle_spec_mismatch_escalation`
  pattern (`orch/daemon/fix_cycle.py:162`).
- The daemon log line shape matches the design doc exactly.
- Operator-preservation logic uses set-diff snapshots
  (`_captured_paths` before and after the cycle), **NOT** `git stash` —
  flag CRITICAL if you find any stash/checkout/revert call in the
  pre/post-cycle paths.
- Empty / missing `scope.allowed_paths` is fail-open (legacy items still
  work).
- The fix-cycle budget counter is NOT incremented when
  `FixCycle.status == FixStatus.escalated` (escalation is a clean exit,
  not a failed retry).

### Verify scope discipline

The implementation must have produced changes ONLY to:

- `orch/daemon/fix_cycle.py`
- `tests/integration/test_fix_cycle_scope_enforcement.py`

Any other file in `git diff` is a CRITICAL finding.

## Verdict

`pass` (proceed to QV gates) or `needs-fix` (loop back to a fix cycle).

## Subagent Result Contract

Standard `code-review-final-impl` JSON.
