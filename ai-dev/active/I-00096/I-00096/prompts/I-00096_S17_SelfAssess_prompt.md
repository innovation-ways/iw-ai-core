# I-00096_S17_SelfAssess_prompt

**Work Item**: I-00096 — Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events
**Step**: S17
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Read-only docker only. No alembic.

## Input Files

- `$IW_ITEM_ID` (env var).
- `.worktrees/I-00096/ai-dev/logs/`
- `ai-dev/active/I-00096/reports/`
- `ai-dev/active/I-00096/I-00096_Issue_Design.md`
- `ai-dev/active/I-00096/I-00096_Functional.md`

## Output Files

- `ai-dev/active/I-00096/reports/I-00096_self_assess_report.md`
- `ai-dev/active/I-00096/reports/I-00096_self_assess_findings.json`

## Context

Run the self-assessment via the `iw-item-analyze` skill. Soft step.

Signals for this incident:

- Did S01 over-suppress the chip (also hiding it on /queue)? Reverse
  regression signal.
- Did the default-filter change break existing tests that assumed
  non-auto-merge events appeared in the table? How many such tests
  needed updates?
- Did S07's CSS-class assertions correctly use attribute scoping or
  did S08 flag them?
- Did `?all=1` propagation through filter+pagination URLs cause
  cycle-back fixes?

## Subagent Result Contract

```json
{
  "step": "S17",
  "agent": "self-assess-impl",
  "work_item": "I-00096",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00096/reports/I-00096_self_assess_report.md",
    "ai-dev/active/I-00096/reports/I-00096_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed."
}
```
