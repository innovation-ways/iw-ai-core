# F-00075_S05_CodeReview_API_prompt

**Work Item**: F-00075 -- MiniMax Coding Plan usage from /coding_plan/remains (replace local SQLite estimate)
**Step**: S05
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits / Migrations off-limits

(Same policy as in S01.)

## Input Files

- `ai-dev/active/F-00075/F-00075_Feature_Design.md`
- `ai-dev/active/F-00075/reports/F-00075_S03_API_report.md`
- `dashboard/routers/usage.py` (post-S03)
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/F-00075/reports/F-00075_S05_CodeReview_API_report.md`

## Context

Per-agent code review of S03 (API). The router change is small; verify it adheres to the design doc and `dashboard/CLAUDE.md`'s "routers are thin" rule.

## Requirements — Review Checklist

- [ ] All three new context keys are passed: `minimax_reset`, `minimax_5h_used`, `minimax_5h_total`.
- [ ] All three use `.get()` (not `[]`) on the MiniMax dict, so a failure-path response (`{"block_pct": 0, "block_reset": None}` only) does not raise `KeyError`.
- [ ] No business logic in the router. The `_bar_color()` helper is unchanged.
- [ ] No new imports introduced (none should be needed).
- [ ] No change to the response type, prefix, or path.
- [ ] `make lint` and `make typecheck` pass.

## Output

Write `F-00075_S05_CodeReview_API_report.md` with:

- Pass/fail per checklist item.
- Severity-tagged findings.
- `approve` or `request_changes`.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "F-00075",
  "completion_status": "complete",
  "review_outcome": "approve|request_changes",
  "findings": [],
  "tests_passed": true,
  "notes": ""
}
```
