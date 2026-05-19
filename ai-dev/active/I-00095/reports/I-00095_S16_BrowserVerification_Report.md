# I-00095 S16 Browser Verification Report

## Environment
- Base URL used: http://localhost:9950
- E2E user: dev@example.local

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | evidences/post/I-00095_v0_preflight.png | `/project/iw-ai-core/auto-merge` had no dangling DOM refs in full-page HTML; no load-time console errors on valid pages. |
| V1 | Sortable headers appear as buttons | pass | null | evidences/post/I-00095_v1_headers.png | Snapshot shows `timestamp`, `event_type`, `entity_id`, `verdict` as buttons; `message` and `actions` remain plain headers. |
| V2 | Clicking timestamp sorts by created_at | pass | null | evidences/post/I-00095_v2_timestamp_sort.png | Timestamp chevron toggled (`↑` then `↓`) across clicks, consistent with created_at direction toggle. |
| V3 | Chevron + aria-sort on active column | pass | null | evidences/post/I-00095_v3_chevron.png | `curl ...sort=event_type&dir=desc` showed exactly one `aria-sort` and a down chevron glyph for active column. |
| V4 | Switching column resets to descending | pass | null | evidences/post/I-00095_v4_switch_col.png | After `event_type` asc, clicking `entity_id` activated `entity_id` with descending chevron (`↓`). |
| V5 | Filter + sort compose | pass | null | evidences/post/I-00095_v5_compose.png | `health_probe` filter applied and table constrained to `auto_merge_health_probe` row(s); sort/filter composition endpoint validated via `type=auto_merge_health_probe&sort=created_at&dir=asc&page=0`. |
| V6 | Invalid sort returns 400 | pass | null | evidences/post/I-00095_v6_400.png | HTTP code was `400`. Response body: `{"detail":"sort must be one of ('created_at', 'event_type', 'entity_id', 'verdict'); got 'message'"}` |
| V7 | No regressions | pass | null | evidences/post/I-00095_v7_no_regressions.png | Filter chip interaction, verdict button click, and `(view)` modal open path still worked. |

## Console / Network Errors
- On intentional invalid endpoint check (V6): `Failed to load resource: the server responded with a status of 400` for `/auto-merge/events?sort=message...`.
- No unexpected load-time console errors observed on normal `/project/iw-ai-core/auto-merge` page flows.

## No Regressions
Observed in adjacent flows on Auto-Merge page:
- Filter chip interaction still re-renders table.
- Verdict button click on first data row still works.
- `(view)` action still opens details modal.

## Screenshots captured
- ai-dev/active/I-00095/evidences/post/I-00095_v0_preflight.png
- ai-dev/active/I-00095/evidences/post/I-00095_v1_headers.png
- ai-dev/active/I-00095/evidences/post/I-00095_v2_timestamp_sort.png
- ai-dev/active/I-00095/evidences/post/I-00095_v3_chevron.png
- ai-dev/active/I-00095/evidences/post/I-00095_v4_switch_col.png
- ai-dev/active/I-00095/evidences/post/I-00095_v5_compose.png
- ai-dev/active/I-00095/evidences/post/I-00095_v6_400.png
- ai-dev/active/I-00095/evidences/post/I-00095_v7_no_regressions.png
