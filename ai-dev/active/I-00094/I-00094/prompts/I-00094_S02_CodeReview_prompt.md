# I-00094_S02_CodeReview_prompt

**Work Item**: I-00094 — Auto-merge htmx-only `<a>` tags render with text cursor and bad accessibility
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00094 --json`
- `ai-dev/active/I-00094/I-00094_Issue_Design.md`
- `ai-dev/active/I-00094/reports/I-00094_S01_Frontend_report.md`
- The three modified fragment templates

## Output Files

- `ai-dev/active/I-00094/reports/I-00094_S02_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Exhaustive conversion** — run the audit grep:

   ```bash
   grep -rn '<a\b[^>]*\bhx-get=' dashboard/templates/fragments/auto_merge_events_table.html dashboard/templates/fragments/auto_merge_event_row.html dashboard/templates/fragments/auto_merge_rollup.html
   ```

   Any match is a CRITICAL finding (S01 missed at least one).

2. **`type="button"` on every new `<button>`** — `<button>` defaults to
   `type="submit"` inside a `<form>`. Without `type="button"`, clicking
   a chip could submit a parent form. CRITICAL if any `<button hx-get>`
   in the changed files lacks `type="button"`.

3. **htmx attribute preservation** — every former `hx-get`, `hx-target`,
   `hx-swap`, `hx-ext` attribute is present on the new `<button>`.

4. **Class preservation** — Tailwind classes carried over verbatim; no
   visual regression.

5. **`href` left intact on real links** — `<a href="…">` elements
   (e.g. the project nav, doc links) MUST NOT have been converted.

6. **No conversion in `auto_merge_event_detail.html`** — that template
   is I-00093's scope and not in S01's allowed paths.

7. **No conversion of verdict pills** — those are already `<button>`
   in `auto_merge_event_row.html` (lines ~11-18); S01 should not have
   touched them.

8. **CSS rule** — if S01 added a normalisation rule to `styles.css`,
   verify it doesn't override Tailwind utilities in unintended ways
   (e.g. `background:transparent` would break `bg-primary` on the
   active chip from I-00092). Use selectors specific enough that
   Tailwind's `bg-primary` still wins on the active chip.

9. **Jinja2 `format` filter discipline** — `%`-style only (I-00075).

### TDD RED Evidence

Frontend step — expected `tdd_red_evidence = "n/a — template-only edits"`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00094",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
