# I-00038 S11 Browser Verification Fix Cycle 2/2

The end-to-end browser verification for step S11 of work item I-00038 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# I-00038 S11 Browser Verification Report

**Step**: S11 (qv-browser)
**Work Item**: I-00038 — Dashboard hangs when multiple tabs are open (SSE connection exhaustion)
**Base URL**: `http://localhost:9941`

## Pass/Fail Summary

| Verification | Name | Status | Notes |
|-------------|------|--------|-------|
| V1 | iwSSE defined + ≤3 SSE conns single tab | ✅ PASS | `window.iwSSE` confirmed present; 1 connection |
| V2 | 6 tabs → ≤3 SSE connections | ❌ FAIL | 5 connections observed (expected ≤3, failure threshold ≥6) |
| V3 | Responsive navigation under multi-tab load | ✅ PASS | Batches link click succeeded in ~1s, no console errors |
| V4 | DaemonEvent fans out to all tabs | ⚠️ AMBIGUOUS | All tabs show `__iwSSEEventCount = 0` before and after injection |
| V5 | No regressions; connection count drops to ~0 when tabs close | ✅ PASS | OSS/status loads cleanly (only 404 for favicon.ico); 1 connection remains after tab close |

## Connection Count Readings

| Step | Condition | Connections | Threshold |
|------|-----------|-------------|-----------|
| V1 | 1 tab open | 1 | ≤3 ✅ |
| V2 | 6 tabs open (all distinct sessions) | 5 | ≤3 ❌ (≥6 = hard fail) |
| V5 | All tabs closed | 1 | ~0 expected (1 actual - likely keepalive) |

## V4 Fan-Out Detail

A `step_failed` DaemonEvent was successfully inserted (DB id 26298, confirmed in DB). After waiting 7+ seconds, no tab's `__iwSSEEventCount` or `__iwSSELastEventType` changed from baseline (all zeros). All tabs show `_worker = false, _fallback = false`.

This could indicate:
1. The SharedWorker is not receiving events from upstream (upstream itself works — event was inserted and detectable)
2. The page template does not call `iwSSE.on('toast', ...)` so no handlers are registered, making fan-out verification indirect
3. The SharedWorker path is active but subscription registration is failing silently

**This needs root-cause analysis before marking V4 as pass.**

## Console Errors

- V5 OSS tab: `404 Not Found @ /favicon.ico:0` — benign, not related to SSE
- No console errors referencing `iwSSE`, SharedWorker, or EventSource in any tab

## Screenshot Evidence

- `ai-dev/active/I-00038/evidences/post/I-00038_v1_single_tab.png` — V1 single tab confirmation
- `ai-dev/active/I-00038/evidences/post/I-00038_v3_responsive_navigation.png` — V3 navigation verification

## Issues Found

### V2 — Connection count 5 with 6 tabs (connection exhaustion not fully resolved)

**File references**:
- `dashboard/static/sse-client.js:142-150` (`_connect()` path selection)
- `dashboard/static/sse-client.js:66-89` (`_initSharedWorker()`)
- `dashboard/static/sse-shared-worker.js:73-119` (SharedWorker connect handler)

**Observation**: With 6 browser tabs open (distinct sessions), `ss` shows 5 established connections to port 9941. The expected ≤3 indicates the SharedWorker is sharing one upstream connection across tabs. A count of 5 is below the ≥6 hard-fail threshold but well above the ≤3 target, suggesting partial regression or a browser-version-specific SharedWorker limitation.

### V4 — Event counter not advancing (fan-out not verified)

**File reference**: `dashboard/static/sse-client.js:21-29` (`_markEventReceived()`)

All tabs report `__iwSSEEventCount = 0` before and after DaemonEvent injection. The SharedWorker `broadcast()` function at `sse-shared-worker.js:37-53` would be a no-op if no ports have active subscriptions. If the page templates do not call `iwSSE.on('toast', handler)`, events sent by the worker would not be observable via `__iwSSELastEventType` / `__iwSSELastEventAt`.

**Recommendation**: Verify that `dashboard/templates/pages/project/*.html` templates call `iwSSE.on('toast', ...)` or similar to register handlers that would trigger `_markEventReceived`.

## Verdict

**Overall: FAIL** — V2 shows the fix is partially effective (5 vs expected ≤3, vs hard-fail ≥6), but V4's ambiguity prevents a clean pass. Recommend deeper investigation into whether the SSE subscription wiring is fully connected before retry.

---

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00038",
  "overall_status": "fail",
  "base_url_used": "http://localhost:9941",
  "verifications": [
    {"id": "V1", "name": "iwSSE defined + ≤3 SSE conns single tab", "status": "pass", "screenshot": "ai-dev/active/I-00038/evidences/post/I-00038_v1_single_tab.png", "notes": "1 connection confirmed"},
    {"id": "V2", "name": "6 tabs → ≤3 SSE connections", "status": "fail", "screenshot": "", "notes": "5 connections (below hard-fail ≥6 but above ≤3 target)"},
    {"id": "V3", "name": "Responsive navigation under multi-tab load", "status": "pass", "screenshot": "ai-dev/active/I-00038/evidences/post/I-00038_v3_responsive_navigation.png", "notes": "Click succeeded, no console errors"},
    {"id": "V4", "name": "DaemonEvent fans out to all tabs", "status": "fail", "screenshot": "", "notes": "__iwSSEEventCount stayed at 0 in all tabs after injection; ambiguous"},
    {"id": "V5", "name": "No regressions; connection count drops to ~0 when tabs close", "status": "pass", "screenshot": "", "notes": "1 connection remains (keepalive), OSS page loads cleanly"}
  ],
  "console_errors_observed": ["404 favicon.ico"],
  "screenshots": [
    "ai-dev/active/I-00038/evidences/post/I-00038_v1_single_tab.png",
    "ai-dev/active/I-00038/evidences/post/I-00038_v3_responsive_navigation.png"
  ],
  "notes": "V2 partial regression: 5 connections instead of ≤3 (but below ≥6 threshold). V4 event counter not advancing - templates may not register toast handlers."
}
```

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/I-00038/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**ESCALATION**: This is the FINAL browser fix cycle (2/2). If you cannot resolve every failing verification, document which remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
