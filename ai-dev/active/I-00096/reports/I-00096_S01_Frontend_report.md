# I-00096_S01_Frontend_report

## What Was Done

**Work Item**: I-00096 — Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events
**Step**: S01 — Frontend implementation

### 1. Suppress duplicate topbar chip on the auto-merge page (Defect a)

**Approach A** was used — explicit flag in the route handler.

- `dashboard/routers/auto_merge_ui.py:auto_merge_page` (line ~95): added `request.state.suppress_topbar_auto_merge_chip = True`
- `dashboard/templates/base.html` (line 196): added `not request.state.suppress_topbar_auto_merge_chip` to the topbar chip conditional guard

This ensures the compact topbar chip is suppressed only on the auto-merge page, while other project pages (queue, batches, etc.) continue to render it normally.

### 2. "Show all daemon events" toggle in the events fragment (Defect b)

- `dashboard/templates/fragments/auto_merge_events_table.html`: Added `{% set _show_all = request.query_params.get('all') in ('1', 'true') %}` and a toggle button rendered via htmx (`hx-get`) that flips the `all` param between `0`/`1`.
- Filter chip URLs now append `&all=1` when `_show_all` is active, so clicking a filter chip doesn't lose the show-all state.
- Pagination Prev/Next URLs also propagate `&all=1` when `_show_all` is active.

### 3. CSS for the toggle button

- `dashboard/static/styles.css`: Added `.auto-merge-show-all-toggle` and `.auto-merge-show-all-toggle.is-active` rules for the toggle button.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/auto_merge_ui.py` | Added `request.state.suppress_topbar_auto_merge_chip = True` in `auto_merge_page` |
| `dashboard/templates/base.html` | Added `not request.state.suppress_topbar_auto_merge_chip` guard to topbar chip conditional |
| `dashboard/templates/fragments/auto_merge_events_table.html` | Added `all` param toggle, filter chip URL propagation, pagination URL propagation |
| `dashboard/static/styles.css` | Added `.auto-merge-show-all-toggle` CSS rules |

## Test Results

```
tests/dashboard/test_auto_merge_routes.py: 37 passed, 0 failed
```

Pre-flight quality gates:
- `make format`: ok (760 files already formatted)
- `make typecheck`: ok (no issues)
- `make lint`: ok (all checks passed)

## TDD Evidence

`tdd_red_evidence = "n/a — template + minor route flag; behavioural tests in S07"`

## Notes

- Approach A was chosen for chip suppression (explicit flag in route handler) rather than Approach B (URL match in template), as it is more explicit and maintainable.
- The `auto_merge_status_chip.html` fragment was NOT modified — the fix targets only the render-site count by suppressing the topbar inclusion.
- The `all` param propagation ensures the toggle state survives filter chip clicks and pagination.