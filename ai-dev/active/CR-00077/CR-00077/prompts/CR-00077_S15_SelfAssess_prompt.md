# CR-00077_S15_SelfAssess_prompt

**Work Item**: CR-00077 -- Overlap details popup (read-only)
**Step**: S15
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits
(Standard policy. Read-only docker introspection is allowed if needed for analysis.)

## ⛔ Migrations: agents generate, daemon applies
This is an analysis step, no DB writes.

## Input Files

- Item id: `$IW_ITEM_ID` (= `CR-00077`).
- Worktree logs: `.worktrees/CR-00077/ai-dev/logs/`.
- Step reports: `ai-dev/active/CR-00077/reports/`.

## Output Files

- `ai-dev/active/CR-00077/reports/CR-00077_self_assess_report.md`
- `ai-dev/active/CR-00077/reports/CR-00077_self_assess_findings.json`

## Context

You are running the self-assessment step for CR-00077. Use the **`iw-item-analyze`** skill to analyze the item's execution history. This step is soft — its failure does not block merge. Produce the best report you can.

## Focus areas specific to CR-00077

When the skill produces findings, ensure the analysis covers:

1. **Single modal partial** — Did S03 build a single clean `batch_overlap_modal.html` partial structured for CR-00078 to extend (per-file Ignore controls on the `<li>` rows + a master button)? Or is the layout rigid enough that CR-00078 would have to rewrite it? Note any refactor CR-00078 would be forced into.
2. **Truncation gap caught early** — Did any test assert the absence of `+N` in the modal body? Or did the verification rely solely on S14 browser_verification? Note whichever case applies.
3. **404 path coverage** — Did S05 cover the 404 path AND did S14 also exercise it (or is one of them missing)?
4. **Fix-cycle cost** — Count the fix cycles per step. If S01 or S03 needed multiple cycles, identify the root cause (template / endpoint contract mismatch, htmx target mismatch, etc.) and propose a workflow improvement.
5. **Scope discipline** — Did the diff stay within `dashboard/` (+ tests)? If `orch/` or `executor/` was touched, that's a CRITICAL finding for the workflow.
6. **Carry-forward** — Does the modal partial's block structure allow CR-00078 to extend it without rewriting? If not, propose a refactor as a CR-00078 prep finding.

## Soft-Step Semantics

This step's failure does NOT block merge. Produce a stub report explaining why if the analysis can't complete.

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "self-assess-impl",
  "work_item": "CR-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00077/reports/CR-00077_self_assess_report.md",
    "ai-dev/active/CR-00077/reports/CR-00077_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
