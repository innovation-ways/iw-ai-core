# F-00086 S16 QvBrowser Summary

## What was done
- Executed browser verification V0..V7 on the isolated E2E stack using `playwright-cli`.
- Captured fresh post-fix screenshots for each verification under `ai-dev/active/F-00086/evidences/post/`.
- Wrote full verification matrix and findings in:
  - `ai-dev/active/F-00086/reports/F-00086_S16_BrowserVerification_Report.md`

## Files changed
- `ai-dev/active/F-00086/reports/F-00086_S16_BrowserVerification_Report.md`
- `ai-dev/active/F-00086/reports/F-00086_S16_QvBrowser_report.md`
- `ai-dev/active/F-00086/evidences/post/F-00086_v0_preflight_sanity.png`
- `ai-dev/active/F-00086/evidences/post/F-00086_v1_create_tab_modal.png`
- `ai-dev/active/F-00086/evidences/post/F-00086_v2_two_tabs_independent.png`
- `ai-dev/active/F-00086/evidences/post/F-00086_v3_tabs_persist_after_reload.png`
- `ai-dev/active/F-00086/evidences/post/F-00086_v4_reopen_from_recent_closed.png`
- `ai-dev/active/F-00086/evidences/post/F-00086_v5_per_tab_abort.png`
- `ai-dev/active/F-00086/evidences/post/F-00086_v6_runtime_dropdown_opencode_only.png`
- `ai-dev/active/F-00086/evidences/post/F-00086_v7_no_regressions.png`

## Test results
- V0, V1, V2, V3, V4, V6, V7: PASS
- V5: FAIL (`code_defect`)

## Issues / observations
- Cross-tab run-state coupling observed in V5: while Tab A streamed, Tab B send stayed disabled, preventing required per-tab interaction.
