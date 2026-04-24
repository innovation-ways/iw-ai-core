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
3. Confirm via server-side probe that the page opened at most one upstream SSE connection to the dashboard port.

   ```bash
   BASE_PORT=$(echo "$IW_BROWSER_BASE_URL" | sed -E 's|^https?://[^:]+:?([0-9]+)?.*|\1|')
   [ -z "$BASE_PORT" ] && BASE_PORT=80
   # ss -tn prints a header line plus one row per connection — N rows ⇒ wc -l = N+1.
   RAW=$(ss -tn state established "( sport = :$BASE_PORT )" | wc -l)
   CONN_COUNT=$(( RAW > 0 ? RAW - 1 : 0 ))
   echo "Connections: $CONN_COUNT"
   ```

   Expected: `CONN_COUNT ≤ 2` (worker upstream + at most one in-flight htmx probe).
4. **Screenshot**: `ai-dev/active/I-00038/evidences/post/I-00038_v1_single_tab.png`.

### V2: Tabs prefer the SharedWorker transport over the per-tab fallback

**Why this V changed.** The earlier version of V2 opened six tabs via
`playwright-cli -s=tab1 … -s=tab6` and asserted the server saw `≤ 3`
established SSE connections. That assertion is **unprovable in this
harness**: each `-s=<name>` spawns a separate Chromium process with its
own profile directory, and `SharedWorker` scope is per-origin + per-browser-
process. Six separate processes → six separate SharedWorker instances →
six upstream connections, *regardless of whether the fix is correct*.
The production claim — "multiple tabs in the same browser share one
connection" — is the subject of the canonical reproduction test at
`tests/dashboard/browser/test_sse_shared_worker.py`
(`test_multi_tab_does_not_exhaust_connection_budget`), which is the
right place to enforce it.

What V2 must verify here: **within a single browser process, the client
picks the SharedWorker transport (not the per-tab fallback EventSource).**
If the SharedWorker path breaks, the client silently falls back and pages
regress to per-tab connections in production too. The client exposes
`window.__iwSSETransport` set to `'shared-worker'` or `'fallback'` for
exactly this check (see `dashboard/static/sse-client.js:_setTransport`).

1. On the tab1 from V1, wait for the transport to be chosen (up to 3 s):

   ```bash
   for _ in 1 2 3 4 5 6; do
     T=$(playwright-cli -s=i00038-tab1 evaluate "window.__iwSSETransport || ''")
     [ -n "$T" ] && [ "$T" != '""' ] && break
     sleep 0.5
   done
   echo "transport: $T"
   ```

2. **Expected: `$T` is the string `"shared-worker"`.** If it is `"fallback"`,
   V2 fails — the `SharedWorker` constructor either threw or the worker
   fired `onerror`, and the client fell back to a per-tab EventSource.
   Check the console snapshot for clues and report the underlying error.
3. Also re-run the connection-count probe from V1 on this single tab —
   it must still be `≤ 2`. A spike here would indicate the client
   somehow has both a SharedWorker *and* a fallback open at the same
   time (a bug that V2 in its old form could not distinguish from the
   playwright-process scope artifact).
4. **Screenshot**: `ai-dev/active/I-00038/evidences/post/I-00038_v2_transport.png`.

### V3: Click-through responsiveness under multi-tab load

The bug this fix addresses is the dashboard hanging when several tabs are
open. Opening distinct `-s=` playwright sessions does not reproduce the
hang (those are separate browser processes), but a useful proxy is to
verify that with two or three extra sessions open, navigation in
`i00038-tab1` is still responsive. Two sessions are enough to catch any
regression in `sse-client.js` init/teardown under concurrent load.

1. Open two more sessions on different pages:

   ```bash
   playwright-cli -s=i00038-tab2 open "$IW_BROWSER_BASE_URL/system/running"
   playwright-cli -s=i00038-tab3 open "$IW_BROWSER_BASE_URL/project/iw-ai-core/batches"
   ```

2. On `i00038-tab1`, snapshot + click a nav link (e.g. Batches):

   ```bash
   playwright-cli -s=i00038-tab1 snapshot
   # pick a nav link ref, e.g. Batches
   playwright-cli -s=i00038-tab1 click <nav-batches-ref>
   ```

3. Verify the page navigates within ~1 s. (`playwright-cli` returns on
   navigation settle; if it hangs, V3 fails.)
4. Confirm no console errors via `playwright-cli -s=i00038-tab1 snapshot`.
5. **Screenshot**: `ai-dev/active/I-00038/evidences/post/I-00038_v3_responsive_navigation.png`.

### V4: DaemonEvent reaches the SSE client (DB → dashboard → client pipeline)

This V proves the end-to-end pipeline: a row inserted into the E2E DB is
picked up by `sse.py:_fetch_new_events`, serialized as `event: toast`, and
stamped on `window.__iwSSEEventCount` via `sse-client.js:_markEventReceived`
inside the dashboard page. One tab is enough to prove the pipeline —
cross-tab fan-out within a single browser process is already covered by
`tests/dashboard/browser/test_sse_shared_worker.py:test_sse_fanout_all_tabs_receive_events`.

1. On `i00038-tab1` (open since V1), record the current event counter:

   ```bash
   BEFORE=$(playwright-cli -s=i00038-tab1 evaluate "window.__iwSSEEventCount || 0")
   echo "before: $BEFORE"
   ```

2. Insert a **toast-eligible** DaemonEvent into the **isolated E2E DB**.
   The event type MUST be one of the `_TOAST_EVENTS` in
   `dashboard/routers/sse.py` (e.g. `step_failed`, `batch_completed`,
   `item_merged`). `step_launched` and other running-update-only types
   are NOT emitted as `toast` and will not bump the counter.

   The dashboard under test polls the **E2E container DB**, not the live
   orchestration DB. The worktree's `.env` points `IW_CORE_DB_*` at the
   live DB, so `orch.db.session.SessionLocal` writes to the wrong place
   and the dashboard never sees the row. Use the DSN the daemon exports
   as `IW_BROWSER_E2E_DB_URL`:

   ```bash
   # $IW_BROWSER_E2E_DB_URL is a standard postgres:// DSN the daemon
   # built from the worktree's allocated e2e-db port. The row lands in
   # the same Postgres the dashboard at $IW_BROWSER_BASE_URL polls.
   uv run python -c "
   import os, psycopg
   from datetime import datetime, UTC
   with psycopg.connect(os.environ['IW_BROWSER_E2E_DB_URL']) as conn:
       with conn.cursor() as cur:
           cur.execute(
               'INSERT INTO daemon_events (event_type, project_id, entity_id, message, metadata, created_at) '
               'VALUES (%s, %s, %s, %s, %s, %s)',
               ('step_failed', 'iw-ai-core', 'I-00038',
                'qv-browser V4 fan-out probe', '{}', datetime.now(UTC)),
           )
       conn.commit()
   "
   ```

   Sanity-check that the row landed in the E2E DB (not the live one):

   ```bash
   uv run python -c "
   import os, psycopg
   with psycopg.connect(os.environ['IW_BROWSER_E2E_DB_URL']) as conn:
       with conn.cursor() as cur:
           cur.execute(\"SELECT id, event_type FROM daemon_events WHERE message = 'qv-browser V4 fan-out probe' ORDER BY id DESC LIMIT 1\")
           print('E2E DB has:', cur.fetchone())
   "
   ```

   If `IW_BROWSER_E2E_DB_URL` is not in the agent env (ancient daemon),
   call `iw step-fail` with a normal reason (not ENV_DATA_MISSING) so a
   fix cycle runs and picks up the missing env var plumbing. The INSERT
   silently succeeding against the live DB is NOT grounds for PASS —
   the sanity check above must confirm the row is in the E2E DB.

3. Wait ~7 s (the SSE generator polls every 5 s).

4. Read the counter again:

   ```bash
   AFTER=$(playwright-cli -s=i00038-tab1 evaluate "JSON.stringify({count: window.__iwSSEEventCount || 0, last: window.__iwSSELastEventType, at: window.__iwSSELastEventAt})")
   echo "after: $AFTER"
   ```

5. Expected: `count` is strictly greater than `$BEFORE` AND `last` is the
   string `"toast"`. If the counter did not advance, V4 fails and the
   fix cycle should inspect `event: error` frames on `/api/stream/events`
   (the SSE generator now surfaces exceptions as errors since I-00038's
   pre-merge state), then trace the DB → dashboard → client hop that
   broke.

6. **Screenshot** the terminal output showing the per-tab before/after counts: `ai-dev/active/I-00038/evidences/post/I-00038_v4_toast_fanout.png`.

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

- **CODE DEFECT** (normal `--reason`, no prefix): an HTTP error, a page showing
  a broken UI, `window.iwSSE` not defined, `window.__iwSSETransport === 'fallback'`
  when the SharedWorker constructor exists, the `toast` event not stamping the
  counter in V4 (with the sanity-check INSERT already confirmed in the E2E DB),
  or a console error referencing the shared worker.
- **ENV_DATA_MISSING** (`--reason "ENV_DATA_MISSING: ..."`): reserved for the
  rare case where the E2E stack is fundamentally incomplete — e.g., the E2E
  DB is unreachable via `$IW_BROWSER_E2E_DB_URL` AND no amount of code or
  fixture editing could reach it. A failure where the agent wrote to the
  wrong DB by using `SessionLocal` is a CODE DEFECT (wrong methodology),
  not ENV_DATA_MISSING. `$IW_BROWSER_E2E_DB_URL` being unset is a CODE
  DEFECT in the daemon (missing env var export), fixable by a fix cycle.

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
