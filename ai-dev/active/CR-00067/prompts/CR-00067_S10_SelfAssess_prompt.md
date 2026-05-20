# CR-00067_S10_SelfAssess_prompt

**Work Item**: CR-00067 — AI Assistant — Context Usage Percentage Indicator
**Step**: S10
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var
- **Worktree logs** — `.worktrees/CR-00067/ai-dev/logs/`
- **Item reports dir** — `ai-dev/work/CR-00067/reports/`

## Output Files

- `ai-dev/work/CR-00067/reports/CR-00067_self_assess_report.md`
- `ai-dev/work/CR-00067/reports/CR-00067_self_assess_findings.json`

## Context

You are running the self-assessment step for work item **CR-00067**.

Use the `iw-item-analyze` skill. Do NOT re-implement the analysis inline.

## Soft-Step Semantics

This step's failure does NOT block merge.

## Subagent Result Contract

```bash
uv run iw step-done CR-00067 --step S10 \
  --report ai-dev/work/CR-00067/reports/CR-00067_self_assess_report.md
```

```json
{
  "step": "S10",
  "agent": "self-assess-impl",
  "work_item": "CR-00067",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00067/reports/CR-00067_self_assess_report.md",
    "ai-dev/work/CR-00067/reports/CR-00067_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": ""
}
```
