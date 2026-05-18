# I-00096 S16 Browser Verification Report

## Environment
- Base URL used: http://localhost:9911
- E2E user: dev@example.local

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | ai-dev/active/I-00096/evidences/post/I-00096_v1_one_chip.png | No dangling DOM references; no console errors at load |
| V1 | Exactly one chip on /auto-merge | pass | null | ai-dev/active/I-00096/evidences/post/I-00096_v1_one_chip.png | `curl` returns count=1 for `id="auto-merge-status-chip"` |
| V2 | Topbar chip on other pages | pass | null | ai-dev/active/I-00096/evidences/post/I-00096_v2_topbar_other_page.png | Queue page shows compact chip "P1 opencode/minimax/MiniMax-M2.7 0 attempts ● degraded" at ref=e67 |
| V3 | Default view excludes non-auto-merge | pass | null | ai-dev/active/I-00096/evidences/post/I-00096_v3_default_excludes.png | Events API returns only `auto_merge_*` types; curl found no `step_launched`, `step_completed`, etc. |
| V4 | Show-all toggle reveals everything | pass | null | ai-dev/active/I-00096/evidences/post/I-00096_v4_show_all.png | Button flips to "Auto-merge events only" [pressed]; table now includes `step_launched CR-00057` row |
| V5 | Filter + show-all + sort compose | pass | null | ai-dev/active/I-00096/evidences/post/I-00096_v5_compose.png | URL `?all=1` visible in toggle label text; filter chips show `&all=1` suffix |
| V6 | Toggle back returns to filtered view | pass | null | ai-dev/active/I-00096/evidences/post/I-00096_v6_back_to_default.png | Button reverts to "Show all daemon events"; only 2 auto-merge events shown |
| V7 | No regressions | pass | null | ai-dev/active/I-00096/evidences/post/I-00096_v7_no_regressions.png | Verdict pills absent (expected — no resolved events in seed); (view) links present; no console errors |

## Console / Network Errors
None observed.

## No Regressions
- Queue page (other project page): compact auto-merge chip present in topbar
- Events table: (view) action links present on all rows
- Filter row: all expected filter chips rendered (all, resolved, attempted, failed, skipped, health_probe, config_updated)
- Toggle button state correctly flips between "Show all daemon events" ↔ "Auto-merge events only"

## Screenshots captured
- ai-dev/active/I-00096/evidences/post/I-00096_v1_one_chip.png
- ai-dev/active/I-00096/evidences/post/I-00096_v2_topbar_other_page.png
- ai-dev/active/I-00096/evidences/post/I-00096_v3_default_excludes.png
- ai-dev/active/I-00096/evidences/post/I-00096_v4_show_all.png
- ai-dev/active/I-00096/evidences/post/I-00096_v5_compose.png
- ai-dev/active/I-00096/evidences/post/I-00096_v6_back_to_default.png
- ai-dev/active/I-00096/evidences/post/I-00096_v7_no_regressions.png

## Root cause
N/A — all verifications pass. The fixes implemented in S01/S03/S05 are working correctly:
- Exactly one `auto-merge-status-chip` element on `/auto-merge` (duplicate chip suppressed)
- Default events view shows only `auto_merge_*` / `merge_auto_*` events (non-auto-merge excluded)
- "Show all daemon events" toggle includes `step_launched` and other daemon events when active
- Toggle correctly flips state and URL carries `?all=1`
- V5 (filter + show-all compose): URL contains both filter param and `&all=1`