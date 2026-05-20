# CR-00063_S05_CodeReview_FIX_Final_prompt

**Work Item**: CR-00063 — Restore Chat Message History on Browser Reload
**Fix Cycle**: 1 of 5
**Final Review That Triggered Fix**: S04

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item has no migrations. N/A.

## Input Files

- `ai-dev/active/CR-00063/CR-00063_CR_Design.md` — Design document (source of truth)
- `ai-dev/active/CR-00063/reports/CR-00063_S04_CodeReview_Final_report.md` — Final review report
- All files referenced in the findings below

## Output Files

- `ai-dev/active/CR-00063/reports/CR-00063_S05_CodeReview_FIX_Final_report.md` — Fix report

## Context

The final cross-agent review (S04) found issues. Address **only** the CRITICAL, HIGH, and MEDIUM (fixable) findings. Read the design document first — it wins over the review's hypothesis.

## Design Doc — Source of Truth (READ FIRST)

`ai-dev/active/CR-00063/CR-00063_CR_Design.md`

## Diagnostic Hypothesis — Findings to Address

{The orchestrator will inject the specific findings from S04 here at runtime.}

## Pre-fix Procedure

1. Read the design doc end-to-end.
2. Diff each affected file against the spec.
3. Apply the minimum patch to align code with the spec.

## Constraints

1. Only fix flagged issues and implement missing requirements.
2. Preserve existing behavior. No regressions.
3. ES5 only — no arrow functions, no `const`/`let`.
4. Run full test suite after fixes.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/ -v -k "chat" --no-header
make lint
```

## Fix Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_FIX_Final",
  "work_item": "CR-00063",
  "fix_cycle": 1,
  "review_step": "S04",
  "findings_addressed": [],
  "findings_skipped": [],
  "missing_requirements_implemented": [],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
