# I-00092_S13_SelfAssess_prompt

**Work Item**: I-00092 — Auto-merge filter chip never highlights the active filter
**Step**: S13
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Read-only docker introspection only. No alembic.

## Input Files

- `$IW_ITEM_ID` (env var).
- `.worktrees/I-00092/ai-dev/logs/`
- `ai-dev/active/I-00092/reports/`
- `ai-dev/active/I-00092/I-00092_Issue_Design.md`
- `ai-dev/active/I-00092/I-00092_Functional.md`

## Output Files

- `ai-dev/active/I-00092/reports/I-00092_self_assess_report.md`
- `ai-dev/active/I-00092/reports/I-00092_self_assess_findings.json`

## Context

Run the self-assessment step for I-00092 using the `iw-item-analyze`
skill (auto-discovered at `.claude/skills/iw-item-analyze/SKILL.md`).
Soft step — failure does NOT block merge; produce a stub with empty
findings if analysis can't complete.

Specific signals for this small-scope incident:

- Did S01's one-line template change actually pass S02 review on first
  try, or did it bounce on lint / `check_templates.py`?
- Did S03's tests use the attribute-scoped CSS class assertion (the
  I-00067 lesson) or did they get re-flagged by S04?
- Did S12 (browser verification) capture all four V1..V4 chip states
  cleanly, or did it `ENV_DATA_MISSING` on event seed availability?

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "self-assess-impl",
  "work_item": "I-00092",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00092/reports/I-00092_self_assess_report.md",
    "ai-dev/active/I-00092/reports/I-00092_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed."
}
```
