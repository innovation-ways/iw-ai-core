# CR-00038 S11 QvBrowser Report

## What Was Done

Browser-based end-to-end verification of the Docs View filter bar redesign and running-jobs strip implementation for CR-00038.

**Steps executed:**
1. Opened browser to `http://localhost:9942/project/iw-ai-core/docs`
2. Performed V0 pre-flight check (dangling DOM refs + console errors)
3. Verified V1: Filter bar is a single row with two `<select>` elements (Type, Status) and a search input — no filter-pill buttons
4. Verified V2: Type dropdown correctly filters the grid (Architecture type → only architecture-map card shown)
5. Verified V3: Type + Status filters combine correctly (Architecture + Published → 1 card)
6. Verified V4: Clicking Regenerate replaces button with disabled grey "Generation queued" and spawns running-jobs strip row with spinner + elapsed timer + Cancel
7. Verified V5: Fresh page load with an existing running job shows the running-jobs strip with doc title, elapsed timer, and Cancel button (seeded via direct SQL since production seed had no running jobs)
8. Verified V6: No regressions — stale-summary, settings gear, select mode, View/Export links all present and functional

## Files Changed / Reviewed

- `ai-dev/active/CR-00038/reports/CR-00038_S11_BrowserVerification_Report.md` — full verification report
- `ai-dev/active/CR-00038/evidences/post/` — 7 PNG screenshots (v0–v6)
- `ai-dev/active/CR-00038/e2e_fixtures/001_running_job.py` — fixture for V5 reproducibility

## Test Results

**All V1–V6 passed.** No failures, no `n/a` entries.

| Verification | Result |
|---|---|
| V0 Pre-flight page sanity | PASS |
| V1 Filter bar single row | PASS |
| V2 Type dropdown filters grid | PASS |
| V3 Combined type+status filters | PASS |
| V4 Generate queued — button disabled + strip row | PASS |
| V5 Strip shows in-progress jobs on page load | PASS |
| V6 No regressions | PASS |

## Issues or Observations

- **V5 seed:** Production pg_dump had no running `DocGenerationJob` rows, so V5 could not be verified without seeding. Solved by inserting a running job directly into the E2E DB: `INSERT INTO doc_generation_jobs ... SELECT 'cr00038-v5-seed-iw-ai-core-architecture-map', ... FROM project_docs WHERE id = 'iw-ai-core:architecture-map'`. The fixture file at `e2e_fixtures/001_running_job.py` documents this for future runs.

- **favicon.ico 404:** Pre-existing console error at page load, not introduced by this CR.

- **Button state on V4:** The Regenerate button correctly transitions to "Generation queued" (disabled grey) after click, confirming the `HX-Trigger: {"docJobCreated": ..., "runningJobsReload": null}` header is working and the running-jobs strip is being triggered via the `runningJobsReload` custom event.

## Screenshots

All screenshots saved to `ai-dev/active/CR-00038/evidences/post/`:
- `CR-00038_v0_preflight.png`
- `CR-00038_v1_filter_bar.png`
- `CR-00038_v2_type_filter.png`
- `CR-00038_v3_combined_filters.png`
- `CR-00038_v4_generate_queued.png`
- `CR-00038_v5_strip_on_load.png`
- `CR-00038_v6_no_regressions.png`