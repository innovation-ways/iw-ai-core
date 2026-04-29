# I-00050_S05_CodeReview_Final_prompt

**Work Item**: I-00050 — Fix cycle prompt carries stale failure report instead of most recent run
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00050/I-00050_Issue_Design.md` — full bug description and acceptance criteria
- `ai-dev/active/I-00050/reports/I-00050_S01_Backend_report.md` — backend fix report
- `ai-dev/active/I-00050/reports/I-00050_S02_CodeReview_Backend_report.md` — per-agent review
- `ai-dev/active/I-00050/reports/I-00050_S03_Tests_report.md` — tests report
- `ai-dev/active/I-00050/reports/I-00050_S04_CodeReview_Tests_report.md` — test review
- `orch/daemon/fix_cycle.py` — the modified file
- `tests/unit/test_fix_cycle.py` — unit tests
- `tests/integration/test_fix_cycle.py` — integration tests

## Output Files

- `ai-dev/active/I-00050/reports/I-00050_S05_CodeReview_Final_report.md` — final review report

## Context

Global cross-layer review of all work done for I-00050. The fix is intentionally small (one function in one file). Verify the fix is correct, complete, and doesn't introduce regressions.

## Review Checklist

### Bug Fix Completeness
- [ ] AC1: `_get_browser_findings` now prepends the latest daemon-detected failure when `StepRun.report_file` is None on the newest failed run
- [ ] AC2: A reproduction test exists and would fail on pre-fix code
- [ ] AC3: When the latest failed run has `report_file` set (agent-reported), output is identical to pre-fix behaviour
- [ ] The original V table content is preserved in the output (fix agents still see V context)

### Implementation Correctness
- [ ] The prepend condition correctly identifies daemon-detected failures: `not latest_failed.report_file`
- [ ] `_truncate` is still applied to the final content
- [ ] No other functions modified (`_latest_failure_reason`, `_get_review_findings`, `attempt_fix_cycle` are unchanged)
- [ ] The "last resort" path (no `report_file`, no `report_content`) still works

### Test Semantic Correctness (CRITICAL — I003 Lesson)
- [ ] Tests verify ORDERING (latest error appears before V table), not just PRESENCE
- [ ] Both the daemon-detected case (prepend occurs) and agent-reported case (no prepend) are covered
- [ ] Integration test uses real DB rows (testcontainer), not mocks
- [ ] Run `make lint` on all changed files — verify zero new violations

### Regression Risk
- [ ] All existing `test_fix_cycle.py` tests still pass (run `make test-unit`)
- [ ] No imports added that could cause circular import issues
- [ ] No change to the `StepRun` or `WorkflowStep` models

## Severity Rubric

| Severity | Meaning |
|----------|---------|
| CRITICAL | Fix logic is wrong (wrong condition, wrong field, breaks existing paths) |
| HIGH | Missing test case for AC3 (no-op path), or test only shape-checks |
| MED | Docstring not updated, or minor code clarity issue |
| LOW | Trivial style |

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00050",
  "overall_status": "pass|fail",
  "mandatory_fix_count": 0,
  "findings": []
}
```

Then call:
```bash
uv run iw step-done I-00050 --step S05 \
  --report ai-dev/active/I-00050/reports/I-00050_S05_CodeReview_Final_report.md
```
