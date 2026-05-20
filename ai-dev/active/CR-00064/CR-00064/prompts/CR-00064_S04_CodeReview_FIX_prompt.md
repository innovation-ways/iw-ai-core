# CR-00064_S04_CodeReview_FIX_prompt

**Work Item**: CR-00064 — Clear Chat History Button in AI Assistant
**Fix Cycle**: 1 of 5
**Original Steps**: S01 (api-impl) + S02 (frontend-impl)
**Review That Triggered Fix**: S03

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item has no migrations. N/A.

## Input Files

- `ai-dev/active/CR-00064/CR-00064_CR_Design.md` — Design document (source of truth)
- `ai-dev/active/CR-00064/reports/CR-00064_S03_CodeReview_report.md` — Review findings
- All files referenced in the findings

## Output Files

- `ai-dev/active/CR-00064/reports/CR-00064_S04_CodeReview_FIX_report.md`

## Context

Address **only** the CRITICAL, HIGH, and MEDIUM (fixable) findings from S03. Read the design doc first — it wins over the review's hypothesis.

## Design Doc — Source of Truth (READ FIRST)

`ai-dev/active/CR-00064/CR-00064_CR_Design.md`

## Diagnostic Hypothesis — Findings to Address

{The orchestrator will inject the specific findings from S03 here at runtime.}

## Constraints

1. Only fix the flagged issues. Do not refactor unrelated code.
2. ES5 only — no arrow functions, no `const`/`let`.
3. Preserve existing behavior.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_chat_clear_button.py tests/dashboard/test_chat_router.py -v
make lint
```

## Fix Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview_FIX",
  "work_item": "CR-00064",
  "fix_cycle": 1,
  "review_step": "S03",
  "findings_addressed": [],
  "findings_skipped": [],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
