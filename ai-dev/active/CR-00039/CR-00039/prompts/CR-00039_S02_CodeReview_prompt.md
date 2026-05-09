# CR-00039_S02_CodeReview_prompt

**Work Item**: CR-00039 — Step Pipeline: Labeled Pill Redesign with Fix-Cycle Expansion
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only introspection (`docker ps`, `docker logs`) is allowed.

## ⛔ Migrations: agents generate, daemon applies

This CR makes no database changes.

---

## Objective

Review the S01 frontend implementation for correctness, completeness, and compliance with
project conventions. Focus on the three changed files.

---

## Input Files

- `ai-dev/active/CR-00039/CR-00039_CR_Design.md` — the design document (acceptance criteria)
- `dashboard/templates/components/step_pipeline.html` — redesigned macro
- `dashboard/templates/fragments/item_overview.html` — duration row removed
- `dashboard/static/styles.css` — new pipeline pill CSS appended

---

## Review Checklist

### Correctness

1. **`data-step-count` preserved** — the outer container in `step_pipeline.html` must still
   carry `data-step-count="{{ steps | length }}"`. Existing tests assert this attribute.

2. **Fix-cycle expansion** — for a step with `fix_cycle_count=2`, the macro must render
   exactly 3 pills: 1 main pill + 2 `↺SXX` amber pills. Verify the Jinja2 `range()` loop
   is correct.

3. **Duration row removed** — the broken `<div class="flex items-center gap-1 mt-2">` block
   and all its children must be absent from `item_overview.html`. The macro call and the
   outer card div must remain.

4. **Status modifier completeness** — confirm that all possible `step.status` values
   (`completed`, `in_progress`, `failed`, `needs_fix`, `skipped`, `pending`) map to a
   valid CSS modifier. Check for an `else` branch that falls back to `--pending`.

5. **Connector logic** — verify no trailing connector is emitted after the last pill overall
   (neither after the last step's main pill if it has no fix cycles, nor after the last
   fix-cycle rerun pill of the last step).

6. **Duration formatting** — confirm the Jinja2 duration format uses integer division
   (`// 60` and `% 60`) and handles the `None` case (no second line rendered).

### CSS quality

7. **`--warning` fallback** — the fix-cycle pill uses `var(--warning, #f59e0b)`. Confirm
   the fallback value is present so the pill renders even if the CSS variable is undefined.

8. **Old classes not clobbered** — `.iw-step-strip` and `.iw-step-seg` must still exist in
   `styles.css`. The new classes are additions, not replacements (backward compat).

9. **`overflow-x: auto`** — the strip container must allow horizontal scrolling on narrow
   viewports. Check it is set either on `.iw-pipeline-strip` or on the wrapping card div.

### Dashboard conventions

10. **No inline styles** — new pills must use CSS classes, not `style=""` attributes.

11. **Tooltips** — each pill (main and fix-cycle) must have a `title` attribute with
    step_id, agent_label, status, and duration (where available).

12. **Accessibility** — pills are purely decorative (the table below is the primary
    data source); `title` is sufficient. No additional ARIA required.

---

## Output

Write a code review report to:
`ai-dev/active/CR-00039/reports/CR-00039_S02_CodeReview_Report.md`

Include:
- A severity-tagged finding for each issue (CRITICAL / HIGH / MEDIUM / LOW / INFO)
- File + line reference for each finding
- A summary pass/fail verdict

Then call:

```bash
# On pass (no CRITICAL/HIGH findings)
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00039/reports/CR-00039_S02_CodeReview_Report.md

# On fail
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short reason>" \
  --report ai-dev/active/CR-00039/reports/CR-00039_S02_CodeReview_Report.md
```
