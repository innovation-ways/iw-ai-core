# I-00097_S13_SelfAssess_prompt

**Work Item**: I-00097 — Auto-merge polish — token cost formatting & entity_id linkification
**Step**: S13
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Read-only docker only. No alembic.

## Input Files

- `$IW_ITEM_ID` (env var).
- `.worktrees/I-00097/ai-dev/logs/`
- `ai-dev/active/I-00097/reports/`
- `ai-dev/active/I-00097/I-00097_Issue_Design.md`
- `ai-dev/active/I-00097/I-00097_Functional.md`

## Output Files

- `ai-dev/active/I-00097/reports/I-00097_self_assess_report.md`
- `ai-dev/active/I-00097/reports/I-00097_self_assess_findings.json`

## Context

Run the self-assessment via the `iw-item-analyze` skill. Soft step —
this is the polish incident, lowest-risk, and most likely to ship
cleanly on first try. If it didn't, that's worth a note in itself.

Signals:

- Did S01 hit the URL-pattern question (singular vs plural items) and
  need to grep the dashboard to find the right convention?
- Did the regex `^(F|I|CR)-\d{5}$` need to be widened to cover any
  other IW prefix (R- for research, BATCH-, etc.) post-review?
- Did S12 ENV_DATA_MISSING on work-item entity_ids?

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "self-assess-impl",
  "work_item": "I-00097",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00097/reports/I-00097_self_assess_report.md",
    "ai-dev/active/I-00097/reports/I-00097_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed."
}
```
