# I-00096_S02_CodeReview_prompt

**Work Item**: I-00096 — Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00096 --json`
- `ai-dev/active/I-00096/I-00096_Issue_Design.md`
- `ai-dev/active/I-00096/reports/I-00096_S01_Frontend_report.md`
- Touched templates + router + CSS

## Output Files

- `ai-dev/active/I-00096/reports/I-00096_S02_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Chip suppression**: the topbar chip is suppressed iff the request
   is for the auto-merge page. Verify by inspecting both:
   - `auto_merge_page` route handler sets the flag.
   - The topbar conditional reads it.
   And check the OTHER project pages (e.g. queue, batches) STILL show
   the compact chip (otherwise S01 over-fixed).
2. **Show-all toggle**: rendered as `<button type="button" hx-get …>`
   with `aria-pressed` and label flip. Class `auto-merge-show-all-toggle`
   matches CSS.
3. **URL propagation**: filter chip URLs and pagination Prev/Next URLs
   include `&all=1` when active. Without this, clicking a filter
   accidentally drops show-all state.
4. **CSS appended to styles.css** (not Tailwind-only).
5. **Jinja2 `format` filter remains `%`-style** (I-00075).
6. **No new `<script>` blocks**.
7. **No accidental changes to `auto_merge_status_chip.html`**.

### TDD RED Evidence

Frontend step — `tdd_red_evidence = "n/a — template + minor route flag"`.

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
  "work_item": "I-00096",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
