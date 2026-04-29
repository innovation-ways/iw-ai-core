# I-00050_S02_CodeReview_Backend_prompt

**Work Item**: I-00050 — Fix cycle prompt carries stale failure report instead of most recent run
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00050/I-00050_Issue_Design.md` — bug description, root cause, acceptance criteria
- `ai-dev/active/I-00050/reports/I-00050_S01_Backend_report.md` — S01 implementation report
- `orch/daemon/fix_cycle.py` — the modified file (review `_get_browser_findings`)

## Output Files

- `ai-dev/active/I-00050/reports/I-00050_S02_CodeReview_Backend_report.md` — review report

## Context

Review the S01 backend fix to `_get_browser_findings` in `orch/daemon/fix_cycle.py`. The fix adds a query for the latest failed `StepRun` and prepends its `error_message` when it represents a newer daemon-detected failure (no `report_file` on the `StepRun`).

## Review Checklist

### Correctness
- [ ] The prepend condition is correct: `not latest_failed.report_file` correctly identifies daemon-detected failures (agent-reported failures always set `StepRun.report_file` via `iw step-fail`)
- [ ] The original report content is preserved (not replaced) — fix agents still see the V table
- [ ] The "last resort" path (no `step.report_file`, no `step.report_content`) is unaffected
- [ ] AC3 is satisfied: when the latest failed run has `report_file` set, output is identical to pre-fix behaviour
- [ ] Run linting on the changed file: `make lint` — verify no ARG001, F811, or other new errors

### Logic
- [ ] The `select()` query uses the correct SQLAlchemy 2.0 style
- [ ] `.scalar_one_or_none()` is used (not `.first()` which is SQLAlchemy 1.x style)
- [ ] `_truncate` is still applied to the final content

### Safety
- [ ] No new DB writes — this function is read-only
- [ ] The fix does not touch `_latest_failure_reason`, `_get_review_findings`, `attempt_fix_cycle`, or any other function
- [ ] No change to the `prior_failure_reason` / ENV_DATA_MISSING suspicion block

### Tests
- [ ] S01 report confirms a RED test existed before the fix
- [ ] The no-op case (latest run has `report_file`) is tested

### Format / Lint
- [ ] Run `make lint` on `orch/daemon/fix_cycle.py` — report any new violations
- [ ] Run `make format --check` on `orch/daemon/fix_cycle.py`

## Severity Rubric

| Severity | Meaning |
|----------|---------|
| CRITICAL | Logic is wrong — the fix makes things worse or breaks a working path |
| HIGH | Missing case, incorrect condition, or test gap that would cause the bug to recur |
| MED | Style deviation, unnecessary complexity, or documentation gap |
| LOW | Trivial nit |

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00050",
  "overall_status": "pass|fail",
  "mandatory_fix_count": 0,
  "findings": []
}
```

Then call:
```bash
uv run iw step-done I-00050 --step S02 \
  --report ai-dev/active/I-00050/reports/I-00050_S02_CodeReview_Backend_report.md
```
