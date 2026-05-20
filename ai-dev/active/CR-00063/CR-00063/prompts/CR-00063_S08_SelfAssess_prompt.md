# CR-00063_S08_SelfAssess_prompt

**Work Item**: CR-00063 — Restore Chat Message History on Browser Reload
**Step**: S08
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source).
- **Worktree logs** — `.worktrees/CR-00063/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00063/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00063/reports/CR-00063_self_assess_report.md`
- `ai-dev/work/CR-00063/reports/CR-00063_self_assess_findings.json`

## Context

You are running the self-assessment step for work item **CR-00063**.

Use the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings. This step is **soft** — failure does NOT block the item from merging.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline.

## Soft-Step Semantics

Failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "self-assess-impl",
  "work_item": "CR-00063",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00063/reports/CR-00063_self_assess_report.md",
    "ai-dev/work/CR-00063/reports/CR-00063_self_assess_findings.json"
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
