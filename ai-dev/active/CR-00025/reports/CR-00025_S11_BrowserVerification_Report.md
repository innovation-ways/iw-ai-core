# CR-00025 S11 Browser Verification Report

**Step**: S11
**Agent**: qv-browser
**Work Item**: CR-00025
**Date**: 2026-04-28
**Base URL**: http://localhost:9911

## Verification Results

| ID | Name | Status | Notes |
|----|------|--------|-------|
| V1 | iw approve ingests pre evidences | **PASS** | Pre gallery shows 1 file (pre_evidence.png, 13.1 KB) after approve |
| V2 | iw step-done for browser_verification ingests post | **PASS** | Post gallery shows 1 file (post_evidence.png, 13.1 KB) after step-done; DB confirms phase='post', step_id='S01' |
| V3 | Post-archive visibility (regression for CR-00020 gap) | **PASS** | After archive with cleanup=False (FS read-only in container), both galleries remain populated from DB |
| V4 | Hard-fail on oversize evidence | **PASS** | approve exits 1 with clear error: "Evidence file 'large_file.png' is 6291456 bytes, exceeds max 5242880 bytes"; DB confirms status='draft', 0 evidence rows |
| V5 | No regressions | **PASS** | F-00055/CR-00001/I-00001 Evidences tabs show empty state as expected; no new console errors |

## Console Errors Observed

- V1-V5: Only `Failed to load resource: 404 (Not Found) @ http://localhost:9911/favicon.ico:0` — this is a pre-existing issue, not related to CR-00025 changes

## Screenshots Captured

All screenshots saved to `ai-dev/active/CR-00025/evidences/post/`:

- `CR-00025_v1_pre_evidence_visible.png` — V1: PRE gallery with 1 file after approve
- `CR-00025_v2_post_evidence_visible.png` — V2: POST gallery with 1 file after step-done
- `CR-00025_v3_post_archive_still_visible.png` — V3: Both galleries still populated after archive
- `CR-00025_v4_oversize_rejected.txt` — V4: Terminal output showing rejection
- `CR-00025_v5_no_regressions.png` — V5: Dashboard page showing no regressions

## Environment Notes

- E2E stack containers: `iw-ai-core-e2e-cr00025-e2e-{db,dashboard,daemon-stub,ollama}-1`
- Archive command could not delete worktree (`/app` mounted read-only in container) — V3 verified DB persistence rather than FS cleanup
- Two fixtures used: CR-99025 (evidence lifecycle test) and CR-99026 (oversize rejection test)

## No Regressions Observed

- Existing work items (F-00055, CR-00001, I-00001) display empty Evidences tab as expected
- No new console errors introduced during verification steps V1-V4
- Evidence ingestion pipeline works correctly for both pre (approve) and post (step-done) phases