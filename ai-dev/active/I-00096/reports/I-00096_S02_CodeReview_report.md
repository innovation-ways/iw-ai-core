# I-00096_S02_CodeReview_report

## Work Item
I-00096 — Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events

## Step Reviewed
S01 (frontend-impl)

## What Was Done

S01 implemented two frontend changes:

1. **Chip deduplication (Defect A)**: Added `request.state.suppress_topbar_auto_merge_chip = True` in the `auto_merge_page` route handler (`dashboard/routers/auto_merge_ui.py:95`), and guarded the topbar chip conditional in `dashboard/templates/base.html` with `not request.state.suppress_topbar_auto_merge_chip`.

2. **"Show all daemon events" toggle (Defect B)**: Added to `auto_merge_events_table.html`:
   - `{% set _show_all = request.query_params.get('all') in ('1', 'true') %}` flag
   - Toggle `<button>` with `hx-get`, `aria-pressed`, label flip (`Show all daemon events` ↔ `Auto-merge events only`)
   - `&all=1` propagated through filter chip URLs, Prev/Next pagination URLs

3. **CSS**: Added `.auto-merge-show-all-toggle` and `.auto-merge-show-all-toggle.is-active` rules to `dashboard/static/styles.css`.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/auto_merge_ui.py` | Added `request.state.suppress_topbar_auto_merge_chip = True` in `auto_merge_page` |
| `dashboard/templates/base.html` | Added `not request.state.suppress_topbar_auto_merge_chip` guard to topbar chip conditional |
| `dashboard/templates/fragments/auto_merge_events_table.html` | Added `all` param toggle, filter chip URL propagation, pagination URL propagation |
| `dashboard/static/styles.css` | Added `.auto-merge-show-all-toggle` CSS rules |

## Review Checklist

### 1. Chip suppression ✅
- `auto_merge_page` route handler sets `request.state.suppress_topbar_auto_merge_chip = True` (line 95).
- `base.html` topbar chip conditional is prefixed with `not request.state.suppress_topbar_auto_merge_chip`.
- Other project pages (queue, batches, etc.) retain the chip because `suppress_topbar_auto_merge_chip` is only set in the auto-merge page route.
- `auto_merge_status_chip.html` was **not modified** (confirmed by `git diff` returning empty).

### 2. Show-all toggle ✅
- Rendered as `<button type="button" hx-get …>` with `aria-pressed="{{ 'true' if _show_all else 'false' }}"` and class `auto-merge-show-all-toggle`.
- Label flips between `Show all daemon events` and `Auto-merge events only`.
- CSS rules appended to `styles.css` (not Tailwind-only).

### 3. URL propagation ✅
- Filter chip URLs include `{% if _show_all %}&all=1{% endif %}`.
- Prev/Next pagination URLs include `{% if _show_all %}&all=1{% endif %}`.
- Without this, clicking a filter chip would drop show-all state — correctly addressed.

### 4. CSS appended to styles.css ✅
- Plain CSS rules, no Tailwind dependency. Per CLAUDE.md "append plain CSS rules directly to `styles.css`" when Tailwind is unavailable.

### 5. Jinja2 `format` filter — `%`-style ✅
- No `|format` calls use `{}`-style. Confirmed by grep across all changed templates — all uses `%dm%02ds` etc.

### 6. No new `<script>` blocks ✅
- No `<script>` tags introduced in any changed template.

### 7. `auto_merge_status_chip.html` unchanged ✅
- `git diff` confirms zero changes to this file.

## Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed (scripts/check_templates.py + ruff) |
| `make format` | ✅ 760 files already formatted |
| `uv run pytest tests/dashboard/test_auto_merge_routes.py -v` | ✅ 37 passed, 0 failed |

**Note on coverage**: The pytest run fails due to total project coverage being below 50% threshold (a pre-existing project-wide condition, not introduced by these changes). All 37 auto-merge route tests pass. The ruff errors in the HTML template linter output are a red herring — `make lint` passes, which is the authoritative gate.

## TDD Evidence
`tdd_red_evidence = "n/a — template + minor route flag; behavioural tests in S07"`

## Notes

- The `ruff check` on individual HTML files reports many "invalid-syntax" errors because ruff's Jinja2 parser is incomplete, but `make lint` (which runs through `scripts/check_templates.py` and the full ruff invocation) passes cleanly. The per-file ruff run is not a valid quality gate.
- S01 chose Approach A (explicit `suppress_topbar_auto_merge_chip` flag) over Approach B (URL-matching in template), which is the more maintainable approach per the design doc.
- The "Show all" toggle URL-building correctly handles the `type` param (appends `&type=…` when a type filter is active) and reverses to auto-merge-only (`&all=1` absent) when deactivated.

## Verdict

**PASS** — S01 correctly implements the frontend portion of I-00096. All review checklist items are satisfied. No mandatory fixes.