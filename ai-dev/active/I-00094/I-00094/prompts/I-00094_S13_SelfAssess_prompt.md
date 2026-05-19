# I-00094_S13_SelfAssess_prompt

**Work Item**: I-00094 — Auto-merge htmx-only `<a>` tags render with text cursor and bad accessibility
**Step**: S13
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Read-only docker only. No alembic.

## Input Files

- `$IW_ITEM_ID` (env var).
- `.worktrees/I-00094/ai-dev/logs/`
- `ai-dev/active/I-00094/reports/`
- `ai-dev/active/I-00094/I-00094_Issue_Design.md`
- `ai-dev/active/I-00094/I-00094_Functional.md`

## Output Files

- `ai-dev/active/I-00094/reports/I-00094_self_assess_report.md`
- `ai-dev/active/I-00094/reports/I-00094_self_assess_findings.json`

## Context

Run the self-assessment via the `iw-item-analyze` skill. Soft step.

Signals:

- Did S01 miss any `<a hx-get>` instances? (Agent thrash signal.)
- Did the normalisation CSS rule (if added) conflict with the
  `bg-primary` active state from I-00092? (Cross-incident regression.)
- Did S11 (integration tests) catch any unexpected click-behaviour
  regression after the `<a>` → `<button>` swap?

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "self-assess-impl",
  "work_item": "I-00094",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00094/reports/I-00094_self_assess_report.md",
    "ai-dev/active/I-00094/reports/I-00094_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed."
}
```
