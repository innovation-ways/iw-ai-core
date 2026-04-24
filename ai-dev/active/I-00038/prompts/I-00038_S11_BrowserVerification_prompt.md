# Browser Verification Prompt: I-00038-S11-BrowserVerification

**Work Item**: I-00038 -- Dashboard hangs when multiple tabs are open (SSE connection exhaustion)
**Step**: S11
**Agent**: qv-browser

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from this worktree. Do NOT attempt to start, stop, or rebuild it yourself.

- **Base URL**: `$IW_BROWSER_BASE_URL`
- **E2E credentials** (if the dashboard ever requires them): `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
- **Work item / step identifiers**: `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports (no `localhost:9900`, no `localhost:9901`). Always use the env var. Do NOT run `make dev`, `make e2e-up`, or any `docker compose` command — the stack is already up. Use `playwright-cli` exclusively (not `agent-browser`, not direct `chromium.launch()`).

## Input Files

- `ai-dev/active/I-00038/I-00038_Issue_Design.md`
- `dashboard/static/sse-shared-worker.js`
- `dashboard/static/sse-client.js`
- `dashboard/templates/base.html`
- `dashboard/templates/pages/project/queue.html`
- `dashboard/templates/pages/project/batches.html`
- `dashboard/templates/pages/project/batch_detail.html`
- `dashboard/templates/pages/project/item_detail.html`
- `dashboard/templates/pages/project/tests.html`
- `dashboard/templates/pages/project/quality.html`
- `dashboard/templates/pages/system/running.html`

## Output Files

- `ai-dev/active/I-00038/reports/I-00038_S11_BrowserVerification_Report.md`
- `ai-dev/active/I-00038/evidences/post/` — screenshots captured during verification

## Prerequisites

Every qv-browser run MUST start with:

```bash
playwright-cli kill-all
playwright-cli -s=i00038-tab1 open "$IW_BROWSER_BASE_URL/project/iw-ai-core/"
```

Then log in if the dashboard requires it (use `snapshot` first to read refs, then `fill` / `click`). On the iw-ai-core dashboard there is no auth, so login is typically a no-op.

Rules:

1. Always call `playwright-cli snapshot` before `fill` / `click`.
2. Use distinct `-s=<name>` session names for each tab so they are genuinely separate browser contexts (otherwise they share state and do not reproduce the real bug).
3. Screenshots go under `ai-dev/active/I-00038/evidences/post/`.

## Verification Steps

### V1: Single tab uses the shared client (no direct EventSource to /api/stream/events)

1. Open one tab: `playwright-cli -s=i00038-tab1 open "$IW_BROWSER_BASE_URL/project/iw-ai-core/"`.
2. Evaluate in the page:

   ```bash
   playwright-cli -s=i00038-tab1 evaluate "typeof window.iwSSE === 'object' && typeof window.iwSSE.on === 'function'"
   ```

   Expected output: `true`.
3. Confirm via server-side probe that exactly one `/api/stream/events` connection exists (the worker's).

   ```bash
   BASE_PORT=$(echo "$IW_BROWSER_BASE_URL" | sed -E 's|^https?://[^:]+:?([0-9]+)?.*|\1|')
   [ -z "$BASE_PORT" ] && BASE_PORT=80
   ss -tn state established "( sport = :$BASE_PORT )" | wc -l
   ```

   Expected: a small number (≤ 3 — worker + maybe a nav-fragment request in flight).
4. **Screenshot**: `ai-dev/active/I-00038/evidences/post/I-00038_v1_single_tab.png`.

### V2: Six tabs do NOT exhaust the per-origin connection budget

1. Open six additional tabs in distinct sessions, each on a different page:

   ```bash
   playwright-cli -s=i00038-tab2 open "$IW_BROWSER_BASE_URL/project/iw-ai-core/batches"
   playwright-cli -s=i00038-tab3 open "$IW_BROWSER_BASE_URL/system/running"
   playwright-cli -s=i00038-tab4 open "$IW_BROWSER_BASE_URL/project/iw-ai-core/tests"
   playwright-cli -s=i00038-tab5 open "$IW_BROWSER_BASE_URL/project/iw-ai-core/quality"
   playwright-cli -s=i00038-tab6 open "$IW_BROWSER_BASE_URL/project/iw-ai-core/"
   ```

2. Give each tab ~2 s to instantiate the SharedWorker (the client's `ready` promise resolves on first connect).
3. Re-probe the server:

   ```bash
   ss -tn state established "( sport = :$BASE_PORT )" | wc -l
   ```

   Expected: still ≤ 3 (NOT 6+). If the count is ≥ 6, V2 fails — the fix has regressed to per-tab connections.
4. **Screenshot** the `ss` output terminal or take a snapshot of one of the tabs: `ai-dev/active/I-00038/evidences/post/I-00038_v2_six_tabs_connection_count.png`.

### V3: Click-through responsiveness under multi-tab load

1. With the 6 tabs still open, switch to `i00038-tab1` and click a link:

   ```bash
   playwright-cli -s=i00038-tab1 snapshot
   # pick a nav link ref, e.g. Batches
   playwright-cli -s=i00038-tab1 click <nav-batches-ref>
   ```

2. Verify the page navigates within ~1 s. (`playwright-cli` returns on navigation settle; if it hangs, V3 fails.)
3. Confirm no console errors via `playwright-cli -s=i00038-tab1 snapshot` (snapshot output includes console logs).
4. **Screenshot**: `ai-dev/active/I-00038/evidences/post/I-00038_v3_responsive_navigation.png`.

### V4: Events fan out to all tabs

1. Trigger a daemon event. The simplest way is to insert a `DaemonEvent` row directly via a short python snippet against the worktree's DB (the isolated E2E stack, not the live orchestrator DB):

   ```bash
   # From the worktree root. The daemon polls and the SSE generator surfaces this.
   uv run python -c "
   from orch.db.session import SessionLocal
   from orch.db.models import DaemonEvent
   import datetime
   db = SessionLocal()
   db.add(DaemonEvent(event_type='step_launched', project_id='iw-ai-core', entity_id='I-00038', message='qv-browser test ping', event_metadata={}, created_at=datetime.datetime.now(datetime.UTC)))
   db.commit()
   "
   ```

   If the E2E stack isolates its own DB and this script would hit the live DB, **STOP** and call `iw step-fail` with `ENV_DATA_MISSING: V4 needs a way to emit a DaemonEvent inside the isolated stack — add an e2e fixture or helper`.
2. Wait ~7 s (SSE generator polls every 5 s).
3. In each tab, evaluate `window.__iwSSELastEventAt` (or a similar client-exposed timestamp if implemented) OR re-snapshot and verify a visible UI change (e.g. a toast appears). The S01 client should expose *something* observable for this verification — if nothing is exposed, use a toast event type and rely on the `#toast-container` DOM:

   ```bash
   for s in i00038-tab1 i00038-tab2 i00038-tab3 i00038-tab4 i00038-tab5 i00038-tab6; do
     playwright-cli -s=$s snapshot | grep -c 'toast-item' || echo "tab $s: no toast"
   done
   ```

4. Expected: every tab shows the toast (or the relevant DOM marker). If any tab is missing it, V4 fails.
5. **Screenshot** one of the tabs showing the toast: `ai-dev/active/I-00038/evidences/post/I-00038_v4_toast_fanout.png`.

### V5: No Regressions

1. Revisit two flows that depend on page-local `EventSource` for job streams (out-of-scope for this fix, must still work):
   - OSS tab: `playwright-cli -s=i00038-oss open "$IW_BROWSER_BASE_URL/project/iw-ai-core/oss/status"` — confirm it loads cleanly.
   - A code-index or docs job panel if available — confirm no console error about `iwSSE` interfering.
2. Close all tabs and re-probe the server:

   ```bash
   ss -tn state established "( sport = :$BASE_PORT )" | wc -l
   ```

   Expected: 0 or near-zero — the SharedWorker closes its upstream when the last port disconnects.
3. **Screenshot**: `ai-dev/active/I-00038/evidences/post/I-00038_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail`.

- **CODE DEFECT** (normal `--reason`): an HTTP error, a page showing a broken UI, `window.iwSSE` not defined, connection count ≥ 6 with 6 tabs open, toast not fanned out to all tabs, or a console error referencing the shared worker.
- **ENV_DATA_MISSING** (`--reason "ENV_DATA_MISSING: ..."`): The E2E stack has no way to emit a `DaemonEvent` (V4 cannot be executed). The fix is an e2e fixture, not a code change.

## Report

Write `ai-dev/active/I-00038/reports/I-00038_S11_BrowserVerification_Report.md` containing:

- Pass/fail table for V1..V5.
- The exact `$IW_BROWSER_BASE_URL` used.
- The connection-count readings from V1, V2, and V5 (the numbers are the core evidence).
- Any issues found, with file:line references if root-caused.
- A list of screenshots captured (relative paths under `evidences/post/`).
- A **No regressions observed** subsection covering V5.

Then call one of:

```bash
# On full pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00038/reports/I-00038_S11_BrowserVerification_Report.md

# On any failure
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/I-00038/reports/I-00038_S11_BrowserVerification_Report.md
```

Always include `--report` on both success and failure.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00038",
  "overall_status": "pass|fail",
  "base_url_used": "",
  "verifications": [
    {"id": "V1", "name": "iwSSE defined + ≤3 SSE conns single tab", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V2", "name": "6 tabs → ≤3 SSE connections", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Responsive navigation under multi-tab load", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V4", "name": "DaemonEvent fans out to all tabs", "status": "pass|fail", "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions; connection count drops to ~0 when tabs close", "status": "pass|fail", "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
