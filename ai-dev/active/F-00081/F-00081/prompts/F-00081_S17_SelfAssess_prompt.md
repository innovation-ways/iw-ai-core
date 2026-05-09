# F-00081_S17_SelfAssess_prompt

**Work Item**: F-00081 -- Per-Item / Per-Step Agent + Model Override
**Step**: S17
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps`/`inspect`/`logs` are allowed; testcontainer fixtures are exempt.

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database. Read-only `alembic history|current|show` is allowed.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/F-00081/ai-dev/logs/` — run logs and fix-cycle logs.
- **Item reports dir** — `ai-dev/active/F-00081/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/active/F-00081/reports/F-00081_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/F-00081/reports/F-00081_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for **F-00081**. This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings.

This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default and you can reference it by name in your reasoning. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S17",
  "agent": "self-assess-impl",
  "work_item": "F-00081",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/F-00081/reports/F-00081_self_assess_report.md",
    "ai-dev/active/F-00081/reports/F-00081_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
