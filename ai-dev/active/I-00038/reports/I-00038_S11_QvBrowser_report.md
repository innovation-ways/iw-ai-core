# I-00038 S11 QvBrowser Report

**Work Item**: I-00038 — Dashboard hangs when multiple tabs are open (SSE connection exhaustion)
**Step**: S11
**Agent**: qv-browser
**Status**: PASS

## What Was Done

Browser-based verification of the SSE SharedWorker fix (I-00038). Five verifications were performed:

- **V1** (Single tab uses shared client): `window.iwSSE` is an object with `.on()` method. SSE connection count = 2 (worker upstream + htmx probe).
- **V2** (Transport selection): `window.__iwSSETransport === "shared-worker"`. The client correctly picks the SharedWorker path, not the per-tab EventSource fallback.
- **V3** (Multi-tab responsiveness): With 3 tabs open, clicking the Batches nav link navigated within ~1 s with no console errors.
- **V4** (DaemonEvent fan-out): A `step_failed` DaemonEvent INSERT into the E2E DB (confirmed at id=1) was delivered as a `toast` event to the browser tab — `count` advanced from 0 to 4, `last="toast"`.
- **V5** (No regressions): OSS tab loaded cleanly (only favicon 404). After closing all tabs, SSE connection count dropped to 0, confirming `closeUpstreamIfIdle` works correctly.

## Files Referenced

- `dashboard/static/sse-client.js` — client with SharedWorker + per-tab fallback
- `dashboard/static/sse-shared-worker.js` — SharedWorker that multiplexes one upstream EventSource
- `ai-dev/active/I-00038/evidences/post/` — 5 screenshots captured

## Screenshots Captured

| File |
|------|
| `evidences/post/I-00038_v1_single_tab.png` |
| `evidences/post/I-00038_v2_six_tabs_connection_count.png` |
| `evidences/post/I-00038_v3_responsive_navigation.png` |
| `evidences/post/I-00038_v4_toast_fanout.png` |
| `evidences/post/I-00038_v5_no_regressions.png` |

## Issues

None.