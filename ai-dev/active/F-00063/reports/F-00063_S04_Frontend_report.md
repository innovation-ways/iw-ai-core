# F-00063 S04 — Frontend Step Report

**Work item**: F-00063 — Stale Process & Migration Detector
**Step**: S04 (frontend-impl)
**Status**: complete

## Summary

Built the staleness dashboard UI: three new template fragments (panel, dot, confirm dialog) wired into the project home and project list pages with htmx self-refresh every 15 seconds. CSS for the red/grey dot lives alongside existing iw-* classes. Tests exhaustively verify rendering for every status combination.

## Files Touched

### New templates
- `dashboard/templates/fragments/staleness_panel.html` — full panel: Migrations section first when present, Services section second, hint copy when both stale, action buttons (Restart/Start/Stop) gated on `actions[]`, htmx self-refresh on the outer `<section>`.
- `dashboard/templates/fragments/staleness_dot.html` — small `<span>` with `iw-staleness-dot[--red|--grey]` classes and htmx 15s refresh; literally empty body for opt-out projects.
- `dashboard/templates/fragments/staleness_confirm.html` — modal body with literal command in `<code>`, Cancel/Confirm buttons matching existing modal style.

### Modified pages
- `dashboard/templates/pages/project/dashboard.html` — embedded `<div hx-get=".../staleness" hx-trigger="load, every 15s">` placeholder near the top of the project content.
- `dashboard/templates/pages/project_selector.html` — embedded per-row `<span hx-get=".../staleness-dot" hx-trigger="load, every 15s">` next to the project name.

### Modified static assets
- `dashboard/static/tailwind.src.css` — added `.iw-staleness-dot`, `.iw-staleness-dot--red`, `.iw-staleness-dot--grey` rules using existing `iw-` prefix conventions.
- `dashboard/static/styles.css` — regenerated via `make css`.

### New tests
- `tests/dashboard/test_staleness_templates.py` — 70 assertions covering opt-out empty render, up-to-date grey dot, stale red dot, panel rendering for every status (`up_to_date`, `stale`, `not_running`, `hot_reload_skipped`, `unknown`), action button gating, migrations section ordering, confirm dialog content + URLs.

## Status Badge Colors

| Status | Color |
|--------|-------|
| `up_to_date` | green |
| `stale` | red |
| `not_running` | grey |
| `hot_reload_skipped` | blue |
| `unknown` | grey |

## Verification

| Gate | Command | Result |
|------|---------|--------|
| Lint | `make lint` | exit 0 |
| Typecheck | `make typecheck` | exit 0 (190 source files) |
| Unit tests | `make test-unit` | 1844 passed, 2 skipped |
| Template tests | `uv run pytest tests/dashboard/test_staleness_templates.py -v` | 41+ passed |

## Notes

- **htmx self-refresh**: the panel `<section>` itself carries `hx-get`/`hx-trigger="every 15s"`/`hx-swap="outerHTML"`, so once loaded it polls itself. The wrapper `<div>` on the project dashboard page only bootstraps the initial load.
- **Empty body for opt-out**: the dot template emits literally nothing (no whitespace, no `<span>`) when the project has no services and no alembic block. htmx replaces the placeholder span with an empty fragment, leaving zero DOM footprint per Invariant 2.
- **Action buttons gated on `actions[]`**: a service with only `restart` configured shows just the Restart button; a service with `start`+`stop` shows both; a service with no commands shows no action buttons (informational only).
- **Confirm dialog**: matches existing modal style from `confirm_action.html`/`archive_batch_dialog.html` — Cancel closes the modal, Confirm fires the POST and closes on response.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "frontend-impl",
  "work_item": "F-00063",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/templates/fragments/staleness_panel.html",
    "dashboard/templates/fragments/staleness_dot.html",
    "dashboard/templates/fragments/staleness_confirm.html",
    "dashboard/templates/pages/project/dashboard.html",
    "dashboard/templates/pages/project_selector.html",
    "dashboard/static/tailwind.src.css",
    "dashboard/static/styles.css",
    "tests/dashboard/test_staleness_templates.py"
  ],
  "tests_passed": true,
  "test_summary": "All template-rendering tests + full unit suite green; lint and typecheck clean.",
  "blockers": [],
  "notes": "Endpoint contract aligned with S03 (template names match: staleness_panel.html, staleness_dot.html, staleness_confirm.html). htmx 15s auto-refresh wired on both panel and dot; opt-out emits zero DOM footprint."
}
```
