# I-00104_S13_SelfAssess_prompt

**Work Item**: I-00104 -- Batch planner false-negative overlap analysis + Max Parallel display mismatch
**Step**: S13
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits
(Read-only docker introspection is allowed.)

## ⛔ Migrations: agents generate, daemon applies
Analysis step only.

## Input Files

- Item id: `$IW_ITEM_ID` (= `I-00104`).
- Worktree logs: `.worktrees/I-00104/ai-dev/logs/`.
- Step reports: `ai-dev/active/I-00104/reports/`.

## Output Files

- `ai-dev/active/I-00104/reports/I-00104_self_assess_report.md`
- `ai-dev/active/I-00104/reports/I-00104_self_assess_findings.json`

## Context

Use the **`iw-item-analyze`** skill. Failure of this step does NOT block merge — produce a stub report if analysis can't complete.

## Focus areas

1. **Helper adoption** — Did the fix really import and call `globs_intersect`, or did it accidentally re-implement the logic inline? Inspect S01's diff via the skill's analysis.
2. **Class-of-bug grep** — Did S05's final review find any other duplicated overlap implementations in the codebase? If so, propose a follow-up finding.
3. **Constant elimination** — Did S05 spot any other `, 4)` literal passed to `generate_execution_plan_md` / `generate_drawio` / `generate_png`? If so, that's a follow-up Incident waiting to happen — surface as a finding.
4. **Test-RED honesty** — Did S03's `tdd_red_evidence` look real, or were the evidences boilerplate? Was the pre-fix RED actually demonstrable from the test design (i.e., did the test target the precise code that S01 changed)?
5. **Fix cycle cost** — How many fix cycles per step? Were any caused by a misread of `globs_intersect`'s return type or argument shape? If so, propose a workflow improvement (e.g. add a docstring example).

## Soft-Step Semantics

This step's failure does NOT block merge.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "self-assess-impl",
  "work_item": "I-00104",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00104/reports/I-00104_self_assess_report.md",
    "ai-dev/active/I-00104/reports/I-00104_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
