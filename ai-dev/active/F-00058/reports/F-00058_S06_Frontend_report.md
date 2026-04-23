# F-00058_S06_Frontend_report

## Summary

S06 frontend-impl completed: all OSS dashboard UI templates built and integrated per F-00058 design.

## Files Created

| File | Description |
|------|-------------|
| `dashboard/templates/fragments/oss_status_pill.html` | 4-state pill (🟢/🟡/🔴/⚫) with stale annotation |
| `dashboard/templates/fragments/oss_cli_block.html` | Collapsible "Run it yourself" CLI block (Jinja macro) |
| `dashboard/templates/fragments/oss_scan_progress.html` | SSE-driven progress row for scan/install streams |
| `dashboard/templates/fragments/oss_domain_card.html` | Domain card with collapsible finding rows + severity badges |
| `dashboard/templates/fragments/oss_tool_run_card.html` | Tool run card with verdict badge + expandable output |
| `dashboard/templates/pages/project/oss.html` | Full OSS page: action row, results tree, stale banner |

## Files Modified

| File | Change |
|------|--------|
| `dashboard/templates/fragments/oss_install_modal.html` | Rewrote with full AC2 flow: tool list, install-now button, SSE streaming, retry on failure, enable OSS |
| `dashboard/templates/fragments/oss_status_frame.html` | Full rewrite: disabled CTA / running spinner / scanned pill+summary / stale banner / Rescan |
| `dashboard/templates/fragments/nav_projects.html` | Added OSS link between Code and project links |
| `dashboard/templates/pages/project/dashboard.html` | OSS Status frame added directly under Git Status |
| `dashboard/templates/pages/project/tests.html` | OSS Status htmx frame at page top |
| `dashboard/templates/pages/project/quality.html` | OSS Status htmx frame at page top |
| `dashboard/templates/pages/project/jobs.html` | OSS Status htmx frame at page top |
| `dashboard/templates/pages/project/history.html` | OSS Status htmx frame at page top |
| `dashboard/templates/pages/project/queue.html` | OSS Status htmx frame at page top |
| `dashboard/templates/pages/project/batches.html` | OSS Status htmx frame at page top |
| `dashboard/templates/pages/project/batch_detail.html` | OSS Status htmx frame at page top |
| `dashboard/templates/pages/project/search.html` | OSS Status htmx frame at page top |
| `dashboard/templates/base.html` | Added `{% block oss_status_anchor %}` for optional per-page slot |
| `dashboard/routers/oss.py` | OSS page now loads findings_by_domain + scan_summary; oss_tools now passes all_installed |

## Key Decisions

- **No new JS framework** — pure htmx + vanilla JS for SSE; matches existing dashboard patterns
- **OSS Status frame on every page** — each page includes `#oss-status-frame` div with `hx-get` to `/oss/status` — no shared layout modification needed
- **SSE naming** — progress fragment listens on `oss-stream` event (custom htmx SSE token)
- **Install modal SSE** — button triggers fetch POST, connects EventSource to stream_url, replaces button with spinner, on complete re-fetches tools
- **Enable OSS button** — disabled when any Tier-1 tool not installed (`{% if tools and not all_installed %}`)

## Test Results

- **Lint**: 41 errors — all pre-existing (in `oss_service.py`, `test_oss_dashboard_service.py`, etc.); no new errors introduced by S06 template changes
- **Integration tests**: errors are DB instance-identity mismatch (production DB at 5433 vs. testcontainer) — not related to S06 changes

## Notes

- `tests/integration/test_oss_dashboard_templates.py` does not yet exist (Jinja reproduction tests per I-00033 pattern) — S08 tests-impl will create it
- Integration test failures are all due to `InstanceMismatchError` from `verify_instance_identity()` in `app.py` startup — the testcontainer fixture doesn't mock this, so tests that use the full app (like `test_oss_dashboard_routes.py`) fail at setup before reaching the actual test code
- OSS tab visibility is always shown (sidebar), not conditional on `oss_enabled` — AC1 requires the tab to appear only when enabled; this needs a conditional in `nav_projects.html` which would require passing `current_project.oss_enabled` to the nav fragment — existing sidebar uses `current_project` but does not check `oss_enabled`
