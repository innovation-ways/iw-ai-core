# CR-00064_S10_SelfAssess_prompt

**Work Item**: CR-00064 — Clear Chat History Button in AI Assistant
**Step**: S10
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var
- **Worktree logs** — `.worktrees/CR-00064/ai-dev/logs/`
- **Item reports dir** — `ai-dev/work/CR-00064/reports/`

## Output Files

- `ai-dev/work/CR-00064/reports/CR-00064_self_assess_report.md`
- `ai-dev/work/CR-00064/reports/CR-00064_self_assess_findings.json`

## Context

Self-assessment for work item **CR-00064**. Use the `iw-item-analyze` skill to analyze execution history. This step is **soft** — failure does NOT block the item from merging.

In Claude Code, invoke via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis inline.

## Subagent Result Contract

```json
{
  "step": "S10",
  "agent": "self-assess-impl",
  "work_item": "CR-00064",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00064/reports/CR-00064_self_assess_report.md",
    "ai-dev/work/CR-00064/reports/CR-00064_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
