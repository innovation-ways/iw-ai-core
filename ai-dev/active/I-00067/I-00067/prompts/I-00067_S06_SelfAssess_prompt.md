# I-00067_S06_SelfAssess_prompt

**Work Item**: I-00067 -- Recent Activity messages need truncation + click-to-expand popup
**Step**: S06
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step is read-only analysis; do not run any alembic command.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/I-00067/ai-dev/logs/`
- **Item reports dir** — `ai-dev/active/I-00067/reports/`

## Output Files

- `ai-dev/active/I-00067/reports/I-00067_self_assess_report.md`
- `ai-dev/active/I-00067/reports/I-00067_self_assess_findings.json`

## Context

Run the self-assessment step for **I-00067**. Use the `iw-item-analyze` skill (auto-discovered via `.claude/skills/iw-item-analyze/SKILL.md`). In Claude Code, invoke via the `Skill` tool with `skill: "iw-item-analyze"`.

Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Soft-Step Semantics

Failure of this step does NOT block merge. If analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "self-assess-impl",
  "work_item": "I-00067",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00067/reports/I-00067_self_assess_report.md",
    "ai-dev/active/I-00067/reports/I-00067_self_assess_findings.json"
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
