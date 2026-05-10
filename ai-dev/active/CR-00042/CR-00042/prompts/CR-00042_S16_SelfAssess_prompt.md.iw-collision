# CR-00042_S16_SelfAssess_prompt

**Work Item**: CR-00042 — Fix Broken "Open full docs" Links in Help Popups
**Step**: S16
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does not touch migrations.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source).
- **Worktree logs** — `.worktrees/CR-00042/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00042/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00042/reports/CR-00042_self_assess_report.md`
- `ai-dev/work/CR-00042/reports/CR-00042_self_assess_findings.json`

## Context

You are running the self-assessment step for work item **CR-00042**.

Use the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings. This step is **soft** — failure does NOT block the item from merging.

## Soft-Step Semantics

Produce the best report you can even if the analysis is partial. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "self-assess-impl",
  "work_item": "CR-00042",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00042/reports/CR-00042_self_assess_report.md",
    "ai-dev/work/CR-00042/reports/CR-00042_self_assess_findings.json"
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
