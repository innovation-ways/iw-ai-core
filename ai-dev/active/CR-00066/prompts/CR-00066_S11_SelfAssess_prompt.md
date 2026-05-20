# CR-00066_S11_SelfAssess_prompt

**Work Item**: CR-00066 — Context Window Usage Progress Bar
**Step**: S11
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var
- **Worktree logs** — `.worktrees/CR-00066/ai-dev/logs/`
- **Item reports dir** — `ai-dev/work/CR-00066/reports/`

## Output Files

- `ai-dev/work/CR-00066/reports/CR-00066_self_assess_report.md`
- `ai-dev/work/CR-00066/reports/CR-00066_self_assess_findings.json`

## Context

You are running the self-assessment step for work item **CR-00066**.

Use the `iw-item-analyze` skill. Do NOT re-implement the analysis inline.

## Soft-Step Semantics

This step's failure does NOT block merge.

## Subagent Result Contract

```bash
uv run iw step-done CR-00066 --step S11 \
  --report ai-dev/work/CR-00066/reports/CR-00066_self_assess_report.md
```

```json
{
  "step": "S11",
  "agent": "self-assess-impl",
  "work_item": "CR-00066",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00066/reports/CR-00066_self_assess_report.md",
    "ai-dev/work/CR-00066/reports/CR-00066_self_assess_findings.json"
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
