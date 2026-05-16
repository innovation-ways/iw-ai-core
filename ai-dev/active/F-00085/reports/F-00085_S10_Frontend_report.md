# F-00085 — S10 Frontend Report

## What was done

- Implemented Auto-Merge UI templates:
  - New page: `pages/project/auto_merge.html`
  - New fragments: status chip, settings, events table, single event row, event detail modal, rollup, refuse-list
- Added Auto-Merge navigation entry in project sidebar links.
- Added base header compact chip include gated on resolved phase (`request.state.auto_merge_phase_for_chip >= 1`).
- Added CSS (plain appended rules, CR-00033 fallback) for:
  - compact/rich status chip,
  - verdict button states,
  - settings widget,
  - refuse-list pills,
  - modal backdrop,
  - diff viewer wrapper.
- Updated auto-merge route test to assert page text renderability (`"Auto-Merge Resolver"`).
- Updated verdict POST fragment response to return a single row fragment for row-level `outerHTML` swaps.

## Files changed

- `dashboard/templates/pages/project/auto_merge.html`
- `dashboard/templates/fragments/auto_merge_status_chip.html`
- `dashboard/templates/fragments/auto_merge_events_table.html`
- `dashboard/templates/fragments/auto_merge_event_row.html`
- `dashboard/templates/fragments/auto_merge_event_detail.html`
- `dashboard/templates/fragments/auto_merge_rollup.html`
- `dashboard/templates/fragments/auto_merge_refuse_list.html`
- `dashboard/templates/fragments/auto_merge_settings.html`
- `dashboard/templates/fragments/nav_projects.html`
- `dashboard/templates/base.html`
- `dashboard/static/styles.css`
- `dashboard/routers/auto_merge_ui.py`
- `tests/dashboard/test_auto_merge_routes.py`

## Test results

- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅ (includes `scripts/check_templates.py`)
- `uv run pytest tests/dashboard/test_auto_merge_routes.py -v` ⚠️ tests pass, but repo-wide coverage gate fails in targeted run context
- `uv run pytest tests/dashboard/test_auto_merge_routes.py -v --no-cov` ✅ 9 passed

## Issues / observations

- Targeted dashboard test execution is green; the default coverage plugin enforces global threshold even for single-file runs, so a `--no-cov` targeted verification run was used for this step-level frontend check.
- Kept phase options strictly to `0` and `1` in settings UI.
- All dynamic sections use htmx attributes; no new standalone JS files were added.
