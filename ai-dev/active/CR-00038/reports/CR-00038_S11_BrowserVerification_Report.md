# CR-00038 S11 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9942`
- **E2E user:** `dev@example.local`
- **Project:** `iw-ai-core`

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | evidences/post/CR-00038_v0_preflight.png | No dangling DOM refs; only favicon.ico 404 (pre-existing) |
| V1 | Filter bar single row | pass | null | evidences/post/CR-00038_v1_filter_bar.png | Type select, Status select, and search input on one row; no filter-pill buttons |
| V2 | Type dropdown filters grid | pass | null | evidences/post/CR-00038_v2_type_filter.png | Selecting "Architecture" shows only architecture-map card |
| V3 | Combined type+status filters | pass | null | evidences/post/CR-00038_v3_combined_filters.png | Architecture + Published shows architecture-map only |
| V4 | Generate queued — button disabled + strip row | pass | null | evidences/post/CR-00038_v4_generate_queued.png | Button became "Generation queued" (disabled grey) with spinner; running-jobs strip appeared below filter bar with doc title, elapsed timer, and Cancel button |
| V5 | Strip shows in-progress jobs on page load | pass | null | evidences/post/CR-00038_v5_strip_on_load.png | Fresh page load shows running-jobs strip with "IW AI Core — Architecture Map" + spinner + elapsed time (0:09) + Cancel button |
| V6 | No regressions | pass | null | evidences/post/CR-00038_v6_no_regressions.png | Stale-summary element present; Settings gear (Documentation settings button) present; Select mode toggle present; View and Export links present on cards |

## Console / Network Errors

- `favicon.ico` 404 at page load — pre-existing, not introduced by this CR
- No new console errors observed during verifications

## No Regressions

### Stale-docs summary row
- Present in HTML (`<div id="stale-summary" ... hx-get="/project/iw-ai-core/api/docs/stale" hx-trigger="load">`), loads via htmx on page load

### Settings gear icon
- `button "Documentation settings" [ref=e69]` — present and clickable

### Select Mode toggle
- `button "Toggle select mode" [ref=e66]` — present

### Export action bar
- Export links present on all doc cards (e.g., `link "Export IW AI Core — Architecture Map"`)

### Card View and Export links
- View and Export links present on all cards; View link navigates to doc detail page

### New JS errors
- No unhandled JS errors observed in `.playwright-cli/console-*.log` beyond pre-existing favicon 404

## Screenshots captured

- `ai-dev/active/CR-00038/evidences/post/CR-00038_v0_preflight.png`
- `ai-dev/active/CR-00038/evidences/post/CR-00038_v1_filter_bar.png`
- `ai-dev/active/CR-00038/evidences/post/CR-00038_v2_type_filter.png`
- `ai-dev/active/CR-00038/evidences/post/CR-00038_v3_combined_filters.png`
- `ai-dev/active/CR-00038/evidences/post/CR-00038_v4_generate_queued.png`
- `ai-dev/active/CR-00038/evidences/post/CR-00038_v5_strip_on_load.png`
- `ai-dev/active/CR-00038/evidences/post/CR-00038_v6_no_regressions.png`

## Root Cause (on failure only)

N/A — all verifications passed.

## Notes

- V5 required a running `DocGenerationJob` to exist in the DB at page load. The seed data (pg_dump from production) had no running jobs, so I inserted one directly via `docker exec` against the E2E DB container: `INSERT INTO doc_generation_jobs (id, project_id, doc_id, status, requested_at) SELECT 'cr00038-v5-seed-iw-ai-core-architecture-map', project_id, id, 'running', NOW() FROM project_docs WHERE id = 'iw-ai-core:architecture-map'`. A fixture file was also created at `ai-dev/active/CR-00038/e2e_fixtures/001_running_job.py` for reproducibility.
- V4 confirmed that clicking Regenerate immediately replaces the button with a disabled grey "Generation queued" button and spawns a running-jobs strip row with spinner, elapsed timer, and Cancel button — all without page reload.