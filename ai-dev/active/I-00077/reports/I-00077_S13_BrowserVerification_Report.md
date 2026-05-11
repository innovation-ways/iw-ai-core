# I-00077 S13 Browser Verification Report

## Environment
- Base URL used: http://localhost:9935
- E2E user: dev@example.local

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | | No dangling DOM refs on /project/iw-ai-core/docs or its detail page; only favicon.ico 404 observed (harmless) |
| V1 | Failed doc job visible on catalogue page | pass | null | evidences/post/I-00077_v1_failed_job_visible.png | Strip shows failed row with red accent, correct error text "job context has no section_guides_snapshot…", and Dismiss button; no spinner / no Cancel / no elapsed timer |
| V2 | Failed-job row dismissible | pass | null | evidences/post/I-00077_v2_failed_row_dismissed.png | Dismiss button (ref=e93) removes row from strip immediately; doc grid remains intact |
| V3 | Running/successful path unchanged | pass | null | evidences/post/I-00077_v3_running_path_unchanged.png | Doc detail page loads HTTP 200; catalogue + detail pages render normally; no console errors |
| V4 | No regressions (filters/search/cards) | pass | null | evidences/post/I-00077_v4_no_regressions.png | Search box filters grid correctly (type "Architecture" → Architecture Diagram card only); filter dropdowns functional |

## Console / Network Errors
Only `favicon.ico:0` 404 — not an application error, not a JavaScript exception, not an HTMX error.

## No Regressions
- Page returned HTTP 200 on all navigations
- Running-jobs strip empty after dismiss (no stale job re-rendered on reload)
- Doc detail page (`/project/iw-ai-core/docs/diagram-architecture`) loads correctly with Regenerate / View / Export controls
- Search and filter controls remain functional

## Screenshots captured
- ai-dev/active/I-00077/evidences/post/I-00077_v1_failed_job_visible.png
- ai-dev/active/I-00077/evidences/post/I-00077_v2_failed_row_dismissed.png
- ai-dev/active/I-00077/evidences/post/I-00077_v3_running_path_unchanged.png
- ai-dev/active/I-00077/evidences/post/I-00077_v4_no_regressions.png

## Root cause (on failure only)
N/A — all verifications passed.

## Fixture
`ai-dev/active/I-00077/e2e_fixtures/001_failed_doc_job.py` seeds `DocGenerationJob` (id=`00000000-0000-0000-0000-000000000077`, status=`failed`, error matches the issue title) and the required `ProjectDoc` (`iw-ai-core:diagram-architecture`). Seed was applied via `docker compose -p iw-ai-core-e2e-i00077 exec e2e-dashboard uv run python scripts/e2e_seed.py` before browser verification.