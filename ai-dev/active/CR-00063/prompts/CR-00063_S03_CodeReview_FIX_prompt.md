# CR-00063_S03_CodeReview_FIX_prompt

**Work Item**: CR-00063 — Restore Chat Message History on Browser Reload
**Fix Cycle**: 1 of 5
**Original Step**: S01 (frontend-impl)
**Review That Triggered Fix**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item has no migrations. N/A.

## Input Files

- `ai-dev/active/CR-00063/CR-00063_CR_Design.md` — Design document (source of truth)
- `ai-dev/active/CR-00063/reports/CR-00063_S02_CodeReview_report.md` — Review report with findings
- All files referenced in the findings below

## Output Files

- `ai-dev/active/CR-00063/reports/CR-00063_S03_CodeReview_FIX_report.md` — Fix report

## Context

The code review for S01 found issues that must be fixed. Address **only** the CRITICAL, HIGH, and MEDIUM (fixable) findings from S02. Read the design document first — it wins over the review's hypothesis when they conflict.

## Design Doc — Source of Truth (READ FIRST)

`ai-dev/active/CR-00063/CR-00063_CR_Design.md` — Read before applying any fix.

## Diagnostic Hypothesis — Findings to Address

{The orchestrator will inject the specific findings from S02 here at runtime.}

## Pre-fix Procedure

1. Read the design doc. Skim the Requirements section.
2. Diff target files against the spec. List deviations before editing.
3. Apply the minimum patch to align code with the spec.
4. If findings disagree with the spec, the spec wins. Note the disagreement.

## Constraints

1. Only fix the flagged issues. Do not refactor unrelated code.
2. Preserve existing behavior. No regressions.
3. ES5 only — no arrow functions, no `const`/`let`.
4. Run tests after every fix.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_chat_history_restore.py tests/dashboard/test_chat_panel_event_protocol.py -v
make lint
```

## Fix Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_FIX",
  "work_item": "CR-00063",
  "fix_cycle": 1,
  "review_step": "S02",
  "findings_addressed": [],
  "findings_skipped": [],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
