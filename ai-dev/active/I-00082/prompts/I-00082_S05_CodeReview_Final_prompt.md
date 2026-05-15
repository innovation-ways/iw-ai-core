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

- `make test-unit -k test_fix_cycle_scope_enforcement` (or `make test-integration -k ...`) passes locally.
- `git diff --stat` shows only `orch/daemon/fix_cycle.py` and the new test file. ANY other file in the diff is scope creep — flag CRITICAL.

### Confirm

- Every AC in the design doc has at least one passing assertion.
- The new `escalate-to-operator` outcome value is used consistently
  everywhere the cycle outcome is consumed (grep the codebase).
- The daemon log line shape matches the design doc exactly.
- Operator-preservation logic does not auto-revert any agent edit.
- Empty / missing `scope.allowed_paths` is fail-open (legacy items still
  work).

### Verify scope discipline

The implementation must have produced changes ONLY to:

- `orch/daemon/fix_cycle.py`
- `tests/integration/test_fix_cycle_scope_enforcement.py`

Any other file in `git diff` is a CRITICAL finding.

## Verdict

`pass` (proceed to QV gates) or `needs-fix` (loop back to a fix cycle).

## Subagent Result Contract

Standard `code-review-final-impl` JSON.
