# I-00038 S11 Browser Verification Report

**Step**: S11 — qv-browser
**Work Item**: I-00038 — Dashboard hangs when multiple tabs are open (SSE connection exhaustion)
**Base URL**: `http://localhost:9941`

## Verification Results

| ID | Name | Status | Notes |
|----|------|--------|-------|
| V1 | iwSSE defined + ≤3 SSE conns single tab | **PASS** | `window.iwSSE` is an object with `.on()` method; connection count = 2 after SSE init |
| V2 | SharedWorker transport selected | **PASS** | `window.__iwSSETransport === "shared-worker"`; connection count = 2 |
| V3 | Responsive navigation under multi-tab load | **PASS** | Batches nav click navigated within ~1 s; no console errors |
| V4 | DaemonEvent fans out to all tabs | **PASS** | `step_failed` INSERT into E2E DB (row confirmed at id=1); after 7 s `count=4`, `last="toast"` |
| V5 | No regressions; connections drop to ~0 | **PASS** | OSS tab loads (only favicon 404); after tab close connections = 0 |

## Connection Count Readings

| Verification | Port | Connections |
|-------------|------|-------------|
| V1 (initial, before SSE init) | 9941 | 2 |
| V2 (after shared-worker transport confirmed) | 9941 | 2 |
| V5 (after all tabs closed) | 9941 | 0 |

## Screenshot Evidence

| File | Verification |
|------|-------------|
| `evidences/post/I-00038_v1_single_tab.png` | V1 — IW AI Core project home after SSE init |
| `evidences/post/I-00038_v2_six_tabs_connection_count.png` | V2 — SSE transport confirmed as `shared-worker` (existing screenshot from earlier run) |
| `evidences/post/I-00038_v3_responsive_navigation.png` | V3 — Batches page navigated with tabs open |
| `evidences/post/I-00038_v4_toast_fanout.png` | V4 — Toast counter advanced (count=4, last="toast") |
| `evidences/post/I-00038_v5_no_regressions.png` | V5 — Project home, no regressions |

## Issues Found

None.

## No Regressions Observed

- **OSS tab** (`/project/iw-ai-core/oss/status`): loads cleanly with only a `favicon.ico 404` (harmless, not related to SSE)
- **Connection cleanup**: after closing all browser tabs, the server-side SSE connection count dropped to 0, confirming the SharedWorker properly closes its upstream connection when the last tab disconnects (`closeUpstreamIfIdle` in `sse-shared-worker.js:66-71`)
- **Console errors**: no errors related to `iwSSE` or the shared worker on any tab

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00038",
  "overall_status": "pass",
  "base_url_used": "http://localhost:9941",
  "verifications": [
    {"id": "V1", "name": "iwSSE defined + ≤3 SSE conns single tab", "status": "pass", "screenshot": "evidences/post/I-00038_v1_single_tab.png", "notes": "conn=2"},
    {"id": "V2", "name": "SharedWorker transport selected", "status": "pass", "screenshot": "evidences/post/I-00038_v2_six_tabs_connection_count.png", "notes": "transport=shared-worker"},
    {"id": "V3", "name": "Responsive navigation under multi-tab load", "status": "pass", "screenshot": "evidences/post/I-00038_v3_responsive_navigation.png", "notes": "nav click succeeded"},
    {"id": "V4", "name": "DaemonEvent fans out to all tabs", "status": "pass", "screenshot": "evidences/post/I-00038_v4_toast_fanout.png", "notes": "count=4 last=toast"},
    {"id": "V5", "name": "No regressions; connection count drops to ~0 when tabs close", "status": "pass", "screenshot": "evidences/post/I-00038_v5_no_regressions.png", "notes": "conn=0 after close"}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "evidences/post/I-00038_v1_single_tab.png",
    "evidences/post/I-00038_v2_six_tabs_connection_count.png",
    "evidences/post/I-00038_v3_responsive_navigation.png",
    "evidences/post/I-00038_v4_toast_fanout.png",
    "evidences/post/I-00038_v5_no_regressions.png"
  ],
  "notes": "All verifications passed. V2 transport remained 'shared-worker' throughout. V4 confirmed E2E DB INSERT was received via SSE toast. Connection count properly drops to 0 when tabs close."
}
```
