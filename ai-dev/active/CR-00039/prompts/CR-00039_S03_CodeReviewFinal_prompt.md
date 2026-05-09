# CR-00039_S03_CodeReviewFinal_prompt

**Work Item**: CR-00039 — Step Pipeline: Labeled Pill Redesign with Fix-Cycle Expansion
**Step**: S03
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only introspection allowed.

## ⛔ Migrations: agents generate, daemon applies

This CR makes no database changes.

---

## Objective

Perform a final cross-agent review of all work produced in CR-00039 (S01 implementation).
Verify overall coherence, that all acceptance criteria are satisfied, and that no issues
were missed by the per-agent review in S02.

---

## Input Files

- `ai-dev/active/CR-00039/CR-00039_CR_Design.md` — design and acceptance criteria
- `ai-dev/active/CR-00039/reports/CR-00039_S02_CodeReview_Report.md` — S02 findings
- `dashboard/templates/components/step_pipeline.html`
- `dashboard/templates/fragments/item_overview.html`
- `dashboard/static/styles.css`

---

## Review Scope

### Cross-layer consistency

1. The macro defined in `step_pipeline.html` is imported in `item_overview.html` with
   `{% from "components/step_pipeline.html" import step_pipeline %}`. Verify the import
   path is correct and the macro name matches.

2. The CSS classes used in the Jinja2 template (`iw-pipeline-strip`, `iw-pipeline-pill`,
   `iw-pipeline-pill--completed`, etc.) must all have corresponding rules in `styles.css`.
   Flag any class referenced in the template that has no CSS definition.

3. The fix-cycle rerun connector class used in the template (`iw-pipeline-connector--fixcycle`)
   must exist in `styles.css`.

### Acceptance criteria verification (trace each AC)

- **AC1** (step IDs visible): the pill renders `step.step_id` in a readable element.
- **AC2** (duration inline, no separate row): duration row absent from `item_overview.html`;
  duration present inside the pill.
- **AC3** (fix cycles expanded): `{% for i in range(step.fix_cycle_count) %}` loop present;
  amber `↺{{ step.step_id }}` pills emitted.
- **AC4** (`data-step-count` preserved): outer container has the attribute.
- **AC5** (table not regressed): the `item_overview.html` step table section (lines ~39–212)
  is unchanged.

### Regression risks

- Verify no other template in `dashboard/templates/` imports `step_pipeline.html` with
  the old macro signature (run `grep -r "step_pipeline" dashboard/templates/`).
- Verify no JS in `dashboard/static/` selects `.iw-step-strip` or `.iw-step-seg` for
  behaviour (run `grep -r "iw-step-strip\|iw-step-seg" dashboard/static/`).

---

## Output

Write a final review report to:
`ai-dev/active/CR-00039/reports/CR-00039_S03_CodeReviewFinal_Report.md`

Then call:

```bash
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00039/reports/CR-00039_S03_CodeReviewFinal_Report.md
```

Or `iw step-fail` if CRITICAL/HIGH issues are found.
