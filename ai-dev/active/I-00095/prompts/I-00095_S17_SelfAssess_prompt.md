# I-00095_S17_SelfAssess_prompt

**Work Item**: I-00095 — Auto-merge events table columns are not sortable
**Step**: S17
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Read-only docker only. No alembic.

## Input Files

- `$IW_ITEM_ID` (env var).
- `.worktrees/I-00095/ai-dev/logs/`
- `ai-dev/active/I-00095/reports/`
- `ai-dev/active/I-00095/I-00095_Issue_Design.md`
- `ai-dev/active/I-00095/I-00095_Functional.md`

## Output Files

- `ai-dev/active/I-00095/reports/I-00095_self_assess_report.md`
- `ai-dev/active/I-00095/reports/I-00095_self_assess_findings.json`

## Context

Run the self-assessment via the `iw-item-analyze` skill. Soft step.

Specific signals for this incident (largest of the six audit fixes):

- Did the whitelist stay consistent across the three layers (aggregator
  / route / template)? If not, where did drift appear?
- Did the verdict NULLS LAST decision cause any test pain?
- Did S05's pagination-URL preservation require fix cycles?
- Did S16's curl-based 400 verification work, or did it surface a
  Pydantic 422 instead (the FastAPI Literal-style pitfall)?

## Subagent Result Contract

```json
{
  "step": "S17",
  "agent": "self-assess-impl",
  "work_item": "I-00095",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00095/reports/I-00095_self_assess_report.md",
    "ai-dev/active/I-00095/reports/I-00095_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed."
}
```
