# I-00097 S12 Browser Verification Report

## Environment
- Base URL used: `http://localhost:9948`
- E2E user: `dev@example.local`

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | — | One hx-target="#auto-merge-status-chip" on /project/iw-ai-core/auto-merge has no matching id in the page; this is a pre-existing condition (base template search bar) and not related to I-00097 changes. No console errors at load time. |
| V1 | Token cost zero renders as $0 | pass | null | evidences/post/I-00097_v1_zero_cost.png | curl confirms `$0` (not `$0.000000`); template fix at auto_merge_rollup.html:22 works correctly. |
| V2 | entity_id link for work-item ID | pass | null | evidences/post/I-00097_v2_link_click.png | CR-00057 renders as `<a href="/project/iw-ai-core/item/CR-00057">` (link, hand pointer in snapshot). Navigation to `/item/CR-00057` returns 404 because CR-00057 does not exist as a DB row (V2 fixture only seeds the DaemonEvent, not the WorkItem). The link structure is correct per spec. |
| V3 | entity_id plain text for non-work-item | pass | null | evidences/post/I-00097_v3_plain_text.png | curl with grep confirms 0 occurrences of `href="/project/.../item/iw-ai-core"`; "iw-ai-core" appears as plain text in config_updated row. |
| V4 | entity_id dash for null | pass | null | evidences/post/I-00097_v4_dash_null.png | health_probe row shows "—" for entity_id (visible in row 176 of auto-merge snapshot: `cell "—" [ref=e193]`). |
| V5 | No regressions | pass | null | evidences/post/I-00097_v5_no_regressions.png | Verdict rollup, token cost rollup, events table all render correctly. No console errors. |

## Console / Network Errors
- `console-2026-05-18T14-09-05-363Z.log`: `Failed to load resource: the server responded with a status of 404 (Not Found) @ http://localhost:9948/project/iw-ai-core/item/CR-00057:0` — this is the V2 navigation to `/item/CR-00057` which is a legitimate 404 since CR-00057 is not a DB row (only the DaemonEvent was seeded). The link structure is correct; the target item simply does not exist in the E2E DB. This is `ENV_DATA_MISSING` for the target, not a code defect.

## No Regressions
Adjacent fragments (`auto_merge_rollup`, `auto_merge_event_row`) render correctly. The `hx-target="#auto-merge-status-chip"` dangling reference is pre-existing (base template search trigger) and unrelated to I-00097. Other pages (verdict rollup, events table with all 3 seeded event types) render correctly with correct cell formatting.

## Screenshots captured
- `ai-dev/active/I-00097/evidences/post/I-00097_v1_zero_cost.png`
- `ai-dev/active/I-00097/evidences/post/I-00097_v2_link_click.png`
- `ai-dev/active/I-00097/evidences/post/I-00097_v3_plain_text.png`
- `ai-dev/active/I-00097/evidences/post/I-00097_v4_dash_null.png`
- `ai-dev/active/I-00097/evidences/post/I-00097_v5_no_regressions.png`

## Root cause (on failure only)
N/A — all verifications pass. The V2 404 is an `ENV_DATA_MISSING` (fixture only seeds DaemonEvent, not the WorkItem row) and not a code defect; the link structure is correct per the spec.

## Fixture Used
`ai-dev/active/I-00097/e2e_fixtures/001_daemon_events.py` — seeds 3 DaemonEvent rows:
- `step_launched` with `entity_id="CR-00057"` (for V2)
- `auto_merge_config_updated` with `entity_id="iw-ai-core"` (for V3)
- `auto_merge_health_probe` with `entity_id=NULL` (for V4)