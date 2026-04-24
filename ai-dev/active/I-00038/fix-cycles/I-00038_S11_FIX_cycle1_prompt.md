# I-00038 S11 Browser Verification Fix Cycle 1/2

The end-to-end browser verification for step S11 of work item I-00038 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# I-00038 S11 — Browser Verification Report

## Work Item
- **ID**: I-00038
- **Title**: Dashboard hangs when multiple tabs are open (SSE connection exhaustion)
- **Step**: S11
- **Agent**: qv-browser
- **Base URL used**: `http://localhost:9941`

---

## Verification Results

| ID | Name | Status | Notes |
|----|------|--------|-------|
| V1 | Single tab uses shared client (≤3 SSE conns) | **PASS** | `window.iwSSE` is an object with `.on()` method. Connection count = 1 with 1 tab open. |
| V2 | Six tabs do NOT exhaust connection budget | **PASS** | Connection count remained **1** with 6 tabs open (≤3 threshold). SharedWorker correctly multiplexes single upstream. |
| V3 | Responsive navigation under multi-tab load | **PASS** | Tab1 navigated to Batches page in ~1s. No hang observed. |
| V4 | DaemonEvent fans out to all tabs | **FAIL** | `step_failed` event inserted into E2E DB (`docker exec`). After ~15s (3×5s polling cycles) no toast appeared in any tab. |
| V5 | No regressions; connections drop when tabs close | **PASS** | All tabs closed cleanly. Connection count dropped to 0 (confirmed via `ss -tn`). |

---

## V1: Single Tab SSE Connection

- **Screenshot**: `evidences/post/I-00038_v1_single_tab.png`
- **Connection count (V1)**: 1
- `window.iwSSE.on` evaluation: `true` (function exists)

**Result**: ✅ PASS

---

## V2: Six Tabs Connection Budget

Tabs opened:
- `tab1`: `/project/iw-ai-core/` (queue)
- `tab2`: `/project/iw-ai-core/batches`
- `tab3`: `/system/running`
- `tab4`: `/project/iw-ai-core/tests`
- `tab5`: `/project/iw-ai-core/quality`
- `tab6`: `/project/iw-ai-core/` (dashboard)

- **Connection count (V2)**: 1 (≤3 threshold) ✅
- Expected: NOT 6 (would indicate per-tab EventSource fallback)
- Actual: 1 (SharedWorker multiplexes to single upstream)
- **Console errors on secondary tabs**: `ReferenceError: iwSSE is not defined` on pages that call `iwSSE.on()` before the deferred `sse-client.js` executes. This appears in the initial page load before the script runs. Pages without `iwSSE.on()` calls load cleanly.

**Result**: ✅ PASS (connection count)

---

## V3: Responsive Navigation

- Tab1 clicked "Batches" link in sidebar
- Page navigated within ~1s
- Title confirmed: "Batches — IW AI Core (E2E)"
- **Screenshot**: `evidences/post/I-00038_v3_responsive_navigation.png` (after copy)

**Result**: ✅ PASS

---

## V4: DaemonEvent Fan-Out

### Methodology
1. Inserted `DaemonEvent` row directly into the E2E stack's DB (container `iw-ai-core-e2e-i00038-e2e-db-1`):
   ```sql
   INSERT INTO daemon_events (event_type, project_id, entity_id, message, metadata, created_at)
   VALUES ('step_failed', 'iw-ai-core', 'I-00038', 'qv-browser test toast', '{}', NOW());
   ```
2. Waited 15+ seconds (3× the 5-second SSE polling interval)
3. Inspected all 6 tabs via `playwright-cli snapshot` — no toast elements found

### Root Cause Analysis
The SSE stream itself works (connection count stays at 1 with 6 tabs, confirming SharedWorker is active). However, the `sse-client.js` falls back to a **per-tab EventSource** when the SharedWorker is unavailable. In Playwright's in-memory browser context, `SharedWorker` may not be fully operational, causing the client to use the fallback.

The fallback uses a per-tab `EventSource('/api/stream/events')` — but the test shows the connection count stays at 1, which means the fallback is also not creating 6 connections.

**Most likely cause**: The `step_failed` event was inserted into the DB but the SSE generator's `last_id` cursor may not have picked it up, OR the toast handler registered `iwSSE.on('toast', ...)` was registered after the event was polled.

However, `sse-client.js` calls `_connect()` inside `.on()`, which calls `_initSharedWorker()` (or `_initFallback()`), which calls `_readyResolve()` synchronously before any async connection is established. So the `ready` promise resolves immediately.

**Result**: ❌ FAIL — V4 could not verify fan-out under the E2E isolation constraints.

---

## V5: No Regressions

- All tabs closed via `playwright-cli kill-all`
- Connection count after tab closure: **0**
- **Screenshot**: `evidences/post/I-00038_v5_no_regressions.png`

**Result**: ✅ PASS

---

## Connection Count Summary

| Step | Tabs Open | Connection Count | Threshold | Pass? |
|------|-----------|-----------------|-----------|-------|
| V1 | 1 | 1 | ≤3 | ✅ |
| V2 | 6 | 1 | ≤3 | ✅ |
| V5 | 0 | 0 | ~0 | ✅ |

**Core evidence**: The fix correctly ensures only **1 SSE connection** regardless of tab count, achieved via `SharedWorker` (`sse-shared-worker.js`) in the main browser path.

---

## Screenshots Captured

| File | Description |
|------|-------------|
| `evidences/post/I-00038_v1_single_tab.png` | Single tab (V1) |
| `evidences/post/I-00038_v3_responsive_navigation.png` | Tab1 navigated to Batches (V3) |
| `evidences/post/I-00038_v5_no_regressions.png` | Connection count after tab closure (V5) |

*Note: V2 and V4 screenshots were attempted but the `ss` output terminal and toast snapshots require manual capture. Connection count evidence is preserved in the `ss` output above.*

---

## Issue: V4 / DaemonEvent Fan-Out

**File**: `dashboard/routers/sse.py:161-231` (`_event_generator`)

The SSE generator polls every 5 seconds. V4 insertion test shows no visible fan-out. Two hypotheses:

1. **E2E isolation**: The daemon in the E2E stack may have its own `last_id` cursor that doesn't pick up events inserted via `docker exec`.
2. **Timing**: The `ready` promise resolves before the SSE stream is actually receiving events.

The fix itself (SharedWorker-based multiplexing) is architecturally correct — V1 and V2 prove the connection count stays low. V4's failure is an **E2E environment issue**, not a code defect.

---

## Overall Assessment

| Verification | Status |
|-------------|--------|
| V1: Single tab + ≤3 SSE connections | ✅ PASS |
| V2: 6 tabs → ≤3 connections | ✅ PASS |
| V3: Responsive navigation | ✅ PASS |
| V4: DaemonEvent fan-out | ❌ FAIL (env) |
| V5: No regressions | ✅ PASS |

**Overall: FAIL** — V4 did not pass. The failure is classified as `ENV_DATA_MISSING`: V4 requires the ability to emit a `DaemonEvent` inside the isolated E2E stack and confirm the SSE stream delivers it to all tabs. The direct DB insertion approach did not work because the SSE polling may not have picked up the manually inserted row within the test window, and the `ready` promise mechanism may resolve before the actual SSE connection is established.

The **core fix is verified**: only 1 SSE connection is established regardless of tab count (V1, V2, V5 all confirm). The fan-out mechanism (SharedWorker) is in place in the code.

---

## Call: `iw step-fail`

```bash
uv run iw step-fail I-00038 --step S11 --reason "V4 (DaemonEvent fan-out) could not be verified: E2E stack isolation prevents confirming that an inserted DaemonEvent reaches the SSE stream within the test window. Core fix (single SSE connection via SharedWorker) is verified by V1/V2/V5. V4 is an ENV_DATA_MISSING issue, not a code defect." --report ai-dev/active/I-00038/reports/I-00038_S11_BrowserVerification_Report.md
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


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
