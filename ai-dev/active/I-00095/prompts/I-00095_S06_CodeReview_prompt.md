# I-00095_S06_CodeReview_prompt

**Work Item**: I-00095 — Auto-merge events table columns are not sortable
**Step Being Reviewed**: S05 (frontend-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00095 --json`
- `ai-dev/active/I-00095/I-00095_Issue_Design.md`
- `ai-dev/active/I-00095/reports/I-00095_S05_Frontend_report.md`
- `dashboard/templates/fragments/auto_merge_events_table.html` (post-S05)
- `dashboard/static/styles.css` (post-S05)

## Output Files

- `ai-dev/active/I-00095/reports/I-00095_S06_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

(Includes `scripts/check_templates.py`.)

## Review Checklist

1. **Sortable columns** — exactly four `<th>` blocks render a
   `<button type="button" hx-get="...">`: `timestamp` (sort=created_at),
   `event_type`, `entity_id`, `verdict`. The `message` and `actions`
   columns remain plain `<th>` text.

2. **`type="button"` on every button** — otherwise it defaults to
   `submit` inside any wrapping `<form>` (there's no form here, but
   defensive practice).

3. **URL construction**:
   - Each sortable button's `hx-get` URL contains
     `page=0&page_size={{ page_size }}&sort={{ col_key }}&dir={{ next_dir }}`.
   - If a filter is active, the URL also carries `&type=…`. Verify the
     template uses `request.query_params.get('type')` to preserve it.
   - Page is reset to 0 on sort change (right behaviour — different
     sort, different page-1 results).

4. **`next_dir` logic**:
   - If clicking the currently-active column: toggle direction
     (desc → asc, asc → desc).
   - If clicking an inactive column: start at `desc`.

5. **Chevron + aria-sort**:
   - Chevron `↓` for desc, `↑` for asc, empty for inactive.
   - `aria-sort="ascending"` / `"descending"` on the active `<th>`.
   - Exactly one `<th>` carries `aria-sort` per render.

6. **Pagination URLs include sort + dir** — Prev/Next links MUST carry
   `&sort={{ sort }}&dir={{ direction }}` so navigation preserves the
   sort. (AC5.)

7. **CSS** — appended to `styles.css`; class names follow `auto-merge-`
   prefix; no conflict with `bg-primary` / `border-primary` (filter
   chips from I-00092).

8. **Jinja2 `format` filter** — any `format` call remains `%`-style
   (I-00075).

9. **No `| safe` filter** added.

### TDD RED Evidence

Frontend step — `tdd_red_evidence = "n/a — template change"`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "I-00095",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
