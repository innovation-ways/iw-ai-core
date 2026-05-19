# I-00093_S13_SelfAssess_prompt

**Work Item**: I-00093 — Auto-merge event detail modal hides the most useful fields
**Step**: S13
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Read-only docker introspection only. No alembic.

## Input Files

- `$IW_ITEM_ID` (env var).
- `.worktrees/I-00093/ai-dev/logs/`
- `ai-dev/active/I-00093/reports/`
- `ai-dev/active/I-00093/I-00093_Issue_Design.md`
- `ai-dev/active/I-00093/I-00093_Functional.md`

## Output Files

- `ai-dev/active/I-00093/reports/I-00093_self_assess_report.md`
- `ai-dev/active/I-00093/reports/I-00093_self_assess_findings.json`

## Context

Run the self-assessment via the `iw-item-analyze` skill (auto-discovered
at `.claude/skills/iw-item-analyze/SKILL.md`). Soft step — failure does
NOT block merge.

Signals for this incident:

- Did S01 hit XSS concerns or `| safe` filter abuse that S02 / S05
  flagged?
- Did the `tojson | tojson` double-encode for the `onclick` clipboard
  call cause any agent confusion (it's an unusual pattern)?
- Did S12 hit `ENV_DATA_MISSING` for resolved events, requiring a
  fixture file?
- Did the existing dashboard tests break due to the new template
  sections (modal HTML shape changed)?

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "self-assess-impl",
  "work_item": "I-00093",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00093/reports/I-00093_self_assess_report.md",
    "ai-dev/active/I-00093/reports/I-00093_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed."
}
```
