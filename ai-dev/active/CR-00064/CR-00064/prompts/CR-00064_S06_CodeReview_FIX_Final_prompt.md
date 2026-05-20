# CR-00064_S06_CodeReview_FIX_Final_prompt

**Work Item**: CR-00064 — Clear Chat History Button in AI Assistant
**Fix Cycle**: 1 of 5
**Final Review That Triggered Fix**: S05

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item has no migrations. N/A.

## Input Files

- `ai-dev/active/CR-00064/CR-00064_CR_Design.md` — Source of truth
- `ai-dev/active/CR-00064/reports/CR-00064_S05_CodeReview_Final_report.md`
- All files referenced in the findings

## Output Files

- `ai-dev/active/CR-00064/reports/CR-00064_S06_CodeReview_FIX_Final_report.md`

## Context

Fix CRITICAL/HIGH/MEDIUM-fixable findings from the final review (S05). Read the design doc first.

## Design Doc — Source of Truth (READ FIRST)

`ai-dev/active/CR-00064/CR-00064_CR_Design.md`

## Diagnostic Hypothesis — Findings to Address

{The orchestrator will inject findings from S05 here at runtime.}

## Constraints

1. Only fix flagged issues and implement missing requirements.
2. ES5 only — no arrow functions, no `const`/`let`.
3. Run full test suite after fixes.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/ -v -k "chat" --no-header
make lint
```

## Fix Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview_FIX_Final",
  "work_item": "CR-00064",
  "fix_cycle": 1,
  "review_step": "S05",
  "findings_addressed": [],
  "findings_skipped": [],
  "missing_requirements_implemented": [],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
