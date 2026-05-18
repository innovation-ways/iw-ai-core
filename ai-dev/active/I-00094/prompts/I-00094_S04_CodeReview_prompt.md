# I-00094_S04_CodeReview_prompt

**Work Item**: I-00094 — Auto-merge htmx-only `<a>` tags render with text cursor and bad accessibility
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00094 --json`
- `ai-dev/active/I-00094/I-00094_Issue_Design.md`
- `ai-dev/active/I-00094/reports/I-00094_S03_Tests_report.md`
- `tests/dashboard/test_auto_merge_routes.py` (post-S03)
- `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00094/reports/I-00094_S04_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Test placement (I-00067)** — every test uses `client` and lives
   under `tests/dashboard/`. CRITICAL otherwise.

2. **Semantic correctness (I003)** — assertions target specific
   structures, not just `"button" in html`:
   - The "negative" regex (`<a hx-get … without href`) is well-formed
     and would actually catch pre-fix HTML.
   - The "positive" regex (`<button type="button" hx-get …`) requires
     `type="button"` explicitly — if S03 didn't, that's a HIGH finding.

3. **All four named tests exist** (design Test to Reproduce + TDD
   Approach):
   - `test_filter_chips_are_buttons_not_hrefless_anchors`
   - `test_view_link_is_button_not_hrefless_anchor`
   - `test_rollup_window_toggles_are_buttons`
   - `test_pagination_links_are_buttons`

   Missing any → HIGH.

4. **Pagination test uses real fixture data** — the test must seed
   ≥51 events so that pagination actually renders Next/Prev. If the
   test asserts on Next without seeding enough rows, it's flaky.

5. **Negative-regex correctness** — `re.findall(r'<a\b(?![^>]*\bhref=)…')`
   is the right shape (negative lookahead on `href`). Common
   miswording: `re.findall(r'<a\b[^>]*\bhx-get=…')` would match BOTH
   anchors with AND without href. Verify the lookahead is present.

6. **Targeted-run discipline** — `tests_passed` from targeted run
   only; not `make test-integration`.

### TDD RED Evidence

Coverage step — `tdd_red_evidence = "n/a — coverage step (tests-impl)"`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

Missing named tests in collection → CRITICAL.

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00094",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
