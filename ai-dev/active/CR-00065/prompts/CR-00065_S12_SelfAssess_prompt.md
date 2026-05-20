# CR-00065_S12_SelfAssess_prompt

**Work Item**: CR-00065 — Live Agent Session Log Viewer
**Step**: S12
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var
- **Worktree logs** — `.worktrees/CR-00065/ai-dev/logs/`
- **Item reports dir** — `ai-dev/work/CR-00065/reports/`

## Output Files

- `ai-dev/work/CR-00065/reports/CR-00065_self_assess_report.md`
- `ai-dev/work/CR-00065/reports/CR-00065_self_assess_findings.json`

## Context

You are running the self-assessment step for work item **CR-00065**.

Use the `iw-item-analyze` skill to perform the analysis. Do NOT re-implement the analysis procedure inline.

## Soft-Step Semantics

This step's failure does NOT block merge. Produce the best report you can even if the analysis is partial.

## Subagent Result Contract

```bash
uv run iw step-done CR-00065 --step S12 \
  --report ai-dev/work/CR-00065/reports/CR-00065_self_assess_report.md
```

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00065",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00065/reports/CR-00065_self_assess_report.md",
    "ai-dev/work/CR-00065/reports/CR-00065_self_assess_findings.json"
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
