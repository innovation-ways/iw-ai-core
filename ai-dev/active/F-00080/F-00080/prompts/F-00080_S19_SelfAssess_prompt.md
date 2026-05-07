# F-00080_S19_SelfAssess_prompt

**Work Item**: F-00080 — First-Time User Onboarding & Contextual Help (Dashboard OSS-readiness)
**Step**: S19
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies. Your job in this step is to ANALYZE the item's execution, not to modify anything.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/F-00080/ai-dev/logs/`
- **Item reports dir** — `ai-dev/work/F-00080/reports/`

## Output Files

- `ai-dev/work/F-00080/reports/F-00080_self_assess_report.md` — Human-readable narrative
- `ai-dev/work/F-00080/reports/F-00080_self_assess_findings.json` — Structured findings

## Context

You are the self-assessment step for work item **F-00080**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history (retries, fix cycles, agent thrash, redundant env/install steps, prompt gaps, manifest issues) and surface process-improvement findings. It is **soft** — failure does not block merge. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered. In Claude Code, invoke via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two output files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis cannot complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S19",
  "agent": "self-assess-impl",
  "work_item": "F-00080",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/F-00080/reports/F-00080_self_assess_report.md",
    "ai-dev/work/F-00080/reports/F-00080_self_assess_findings.json"
  ],
  "preflight": {
    "format": "skipped:no-code-changes",
    "typecheck": "skipped:no-code-changes",
    "lint": "skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
