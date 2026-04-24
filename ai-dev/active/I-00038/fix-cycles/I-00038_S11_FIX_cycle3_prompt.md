# I-00038 S11 Browser Verification Fix Cycle 3/3

The end-to-end browser verification for step S11 of work item I-00038 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# I-00038 S11 Browser Verification Report

## Summary

Work Item: I-00038 -- Dashboard hangs when multiple tabs open (SSE connection exhaustion)
Step: S11
Agent: qv-browser
Base URL: http://localhost:9941

## Verification Results

| ID | Name | Status | Notes |
|----|------|--------|-------|
| V1 | Single tab uses shared client | **PASS** | iwSSE defined correctly, 1 SSE connection |
| V2 | 6 tabs do NOT exhaust connection budget | **FAIL** | 6 connections with 6 tabs (≥6 threshold = per-tab connections) |
| V3 | Responsive navigation under load | **PASS** | Navigation completed without hang, no console errors |
| V4 | Events fan out to all tabs | **FAIL** | Tab6 received 0 events (others received 2-4) |
| V5 | No regressions | **PASS** | OSS status loads, connections drop after close |

## Connection Count Evidence

| Verification | Tabs Open | Connection Count | Pass/Fail |
|-------------|-----------|------------------|-----------|
| V1 | 1 | 1 | PASS (≤3) |
| V2 | 6 | 6 | FAIL (≥6 = per-tab connections) |
| V5 | 0 (after close) | ~0 | PASS (near-zero) |

## Detailed Findings

### V2 Failure
With 6 tabs open, `ss` showed 6 established connections to the dashboard port. The fix criteria state: "If the count is ≥ 6, V2 fails — the fix has regressed to per-tab connections."

This suggests the SharedWorker SSE multiplexing is not functioning correctly — each tab appears to maintain its own SSE connection rather than sharing one connection via the SharedWorker.

### V4 Failure (Tab6 Fan-out)
After injecting `step_failed` event into E2E DB:
- tab1: count=4, last=toast ✓
- tab2: count=4, last=toast ✓
- tab3: count=4, last=toast ✓
- tab4: count=2, last=toast ✓
- tab5: count=2, last=toast ✓
- tab6: count=0, last=null ✗

Tab6 did not receive the toast event despite being open on the same `/project/iw-ai-core/` URL as tab1. This indicates inconsistent event delivery across tabs sharing the same SharedWorker.

## Console Errors Observed
- V5 (OSS tab): 404 for `/favicon.ico` — benign, not related to SSE fix

## Screenshots Captured
- `evidences/post/I-00038_v1_single_tab.png` — V1 verification
- `evidences/post/I-00038_v2_six_tabs_connection_count.png` — V2 browser state
- `evidences/post/I-00038_v3_responsive_navigation.png` — V3 navigation test
- `evidences/post/I-00038_v4_toast_fanout.png` — V4 fan-out test

## Root Cause Analysis

V2 and V4 failures suggest the SharedWorker implementation in `sse-shared-worker.js` may not be properly:
1. Establishing a single shared SSE connection
2. Broadcasting events to all connected tabs

Key files to investigate:
- `dashboard/static/sse-shared-worker.js` — SharedWorker implementation
- `dashboard/static/sse-client.js` — Client that connects to shared worker

## Verdict

**FAIL** — V2 and V4 failures indicate the SSE connection sharing fix has regressed or is not functioning correctly. The per-tab connection count (6 with 6 tabs) and inconsistent event fan-out (tab6 receiving 0 events) require investigation before this fix can be marked complete.

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00038",
  "overall_status": "fail",
  "base_url_used": "http://localhost:9941",
  "verifications": [
    {"id": "V1", "name": "iwSSE defined + ≤3 SSE conns single tab", "status": "pass", "screenshot": "evidences/post/I-00038_v1_single_tab.png", "notes": ""},
    {"id": "V2", "name": "6 tabs → ≤3 SSE connections", "status": "fail", "screenshot": "evidences/post/I-00038_v2_six_tabs_connection_count.png", "notes": "6 connections with 6 tabs = per-tab connections, not shared"},
    {"id": "V3", "name": "Responsive navigation under multi-tab load", "status": "pass", "screenshot": "evidences/post/I-00038_v3_responsive_navigation.png", "notes": ""},
    {"id": "V4", "name": "DaemonEvent fans out to all tabs", "status": "fail", "screenshot": "evidences/post/I-00038_v4_toast_fanout.png", "notes": "Tab6 received 0 events, others received 2-4"},
    {"id": "V5", "name": "No regressions; connection count drops to ~0 when tabs close", "status": "pass", "screenshot": "", "notes": "OSS status loads, connections near 0 after close"}
  ],
  "console_errors_observed": ["404 /favicon.ico (benign)"],
  "screenshots": [
    "evidences/post/I-00038_v1_single_tab.png",
    "evidences/post/I-00038_v2_six_tabs_connection_count.png",
    "evidences/post/I-00038_v3_responsive_navigation.png",
    "evidences/post/I-00038_v4_toast_fanout.png"
  ],
  "notes": "V2 and V4 failures indicate SSE connection sharing not working correctly"
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
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00038/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**ESCALATION**: This is the FINAL browser fix cycle (3/3). If you cannot resolve every failing verification, document which remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
