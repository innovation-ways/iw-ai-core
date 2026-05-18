# I-00096 S16 QvBrowser Report

## What was done
Executed browser-based end-to-end verifications (V0–V7) against the `/project/iw-ai-core/auto-merge` page using `playwright-cli`. All 7 verifications passed.

## Files changed
None — this was a verification-only step.

## Test results

| V | Description | Result |
|---|-------------|--------|
| V0 | Pre-flight page sanity | ✅ PASS |
| V1 | Exactly one chip on /auto-merge | ✅ PASS |
| V2 | Topbar chip on other pages | ✅ PASS |
| V3 | Default view excludes non-auto-merge | ✅ PASS |
| V4 | Show-all toggle reveals everything | ✅ PASS |
| V5 | Filter + show-all + sort compose | ✅ PASS |
| V6 | Toggle back returns to filtered view | ✅ PASS |
| V7 | No regressions | ✅ PASS |

**Overall: PASS** — all 8 verifications (V0–V7) passed without failure.

## Key observations
- `id="auto-merge-status-chip"` appears exactly once on the auto-merge page (no duplicate chip)
- The compact topbar chip appears on the `/queue` page as expected
- Default events view shows only `auto_merge_*` event types; no `step_launched`, `step_completed`, etc.
- "Show all daemon events" toggle correctly (a) changes button label to "Auto-merge events only" [pressed], (b) reveals `step_launched` rows in the table, (c) appends `?all=1` to the URL
- Clicking back returns to the filtered view with only auto-merge events
- No console errors observed throughout V1–V6

## Issues or observations
None.