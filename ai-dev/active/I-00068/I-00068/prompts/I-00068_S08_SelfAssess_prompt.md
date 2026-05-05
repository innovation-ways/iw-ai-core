# I-00068_S08_SelfAssess_prompt

**Work Item**: I-00068 -- Recent Activity batch link from "archived" event routes to /item/ instead of /batch/
**Step**: S08
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step is read-only analysis.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/I-00068/ai-dev/logs/`
- **Item reports dir** — `ai-dev/active/I-00068/reports/`

## Output Files

- `ai-dev/active/I-00068/reports/I-00068_self_assess_report.md`
- `ai-dev/active/I-00068/reports/I-00068_self_assess_findings.json`

## Context

Run the self-assessment step for **I-00068**. Use the `iw-item-analyze` skill (auto-discovered via `.claude/skills/iw-item-analyze/SKILL.md`). In Claude Code, invoke via the `Skill` tool with `skill: "iw-item-analyze"`.

Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract.

## Soft-Step Semantics

Failure of this step does NOT block merge. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "self-assess-impl",
  "work_item": "I-00068",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00068/reports/I-00068_self_assess_report.md",
    "ai-dev/active/I-00068/reports/I-00068_self_assess_findings.json"
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
