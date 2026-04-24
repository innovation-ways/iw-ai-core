# I-00038_S01_Frontend_prompt

**Work Item**: I-00038 -- Dashboard hangs when multiple tabs are open (SSE connection exhaustion)
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards. No docker or alembic mutation commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00038/I-00038_Issue_Design.md` — read **Description**, **Root Cause Analysis**, **Affected Components**, and **Acceptance Criteria**.
- `dashboard/routers/sse.py` — server-side stream (read only; do NOT modify). Note the event types emitted: `running-update`, `status-update`, `test-update`, `quality-update`, `toast`.
- `dashboard/templates/base.html` — base layout where the shared client must be loaded.
- `dashboard/templates/components/toast.html` — the toast helper `showToast()` is defined here and is loaded globally.
- The 7 page templates to migrate:
  - `dashboard/templates/pages/project/queue.html`
  - `dashboard/templates/pages/project/batches.html`
  - `dashboard/templates/pages/project/batch_detail.html`
  - `dashboard/templates/pages/project/item_detail.html`
  - `dashboard/templates/pages/project/tests.html`
  - `dashboard/templates/pages/project/quality.html`
  - `dashboard/templates/pages/system/running.html`
- `CLAUDE.md` (project root) and `dashboard/CLAUDE.md` — conventions and hard rules.

## Output Files

- `dashboard/static/sse-shared-worker.js` — new SharedWorker script.
- `dashboard/static/sse-client.js` — new client-side API (`window.iwSSE`).
- `dashboard/templates/base.html` — `<script>` include for `sse-client.js`.
- Edits to all 7 page templates above (replace `new EventSource('/api/stream/events')` + `es.addEventListener(...)` with `iwSSE.on(...)` calls).
- `ai-dev/active/I-00038/reports/I-00038_S01_Frontend_report.md` — step report.

## Context

Users' browsers hang after ~6 dashboard tabs are open because each tab opens its own `EventSource('/api/stream/events')`, exhausting the per-origin HTTP/1.1 connection budget. Fix: multiplex a single upstream SSE connection across all tabs using a **SharedWorker**, with a per-tab fallback to direct `EventSource` when SharedWorker is unavailable.

Read `I-00038_Issue_Design.md` first for the full picture.

## Requirements

### 1. `dashboard/static/sse-shared-worker.js`

A SharedWorker that:

- Maintains **one** `EventSource('/api/stream/events')` for its entire lifetime.
- Starts the upstream connection lazily on the first port `connect` (do not eagerly open on worker boot).
- Accepts messages from each connected port:
  - `{type: 'subscribe', events: ['running-update', 'toast', ...]}` — record which event types each port wants.
  - `{type: 'unsubscribe'}` — stop sending to that port (optional; port close also works).
  - `{type: 'ping'}` → replies `{type: 'pong'}` (used by the client for liveness).
- On each incoming upstream event, fans out to every connected port whose subscription set includes that event type as `{type: 'sse', event: '<type>', data: '<raw data string>', id: '<last-event-id>'}`.
- Tracks the set of connected ports and stops the upstream `EventSource` when the last port disconnects (`port.onmessage` receives `{type: 'close'}` or the `close` event triggers via message-channel teardown — whichever works reliably). This frees the connection while the dashboard is idle.
- Handles upstream errors: if `EventSource.onerror` fires, let the native `EventSource` auto-reconnect; on repeated failures, notify all ports with `{type: 'sse-error'}` so clients can surface a soft warning if they want (but do not block).
- Must be valid JavaScript — will be checked by `node --check` (no ES module syntax unless the worker script itself is self-contained).

Skeleton reference (for guidance, not a copy-paste):

```javascript
// SharedWorker global scope: addEventListener('connect', ...)
let upstream = null;
const ports = new Map(); // port -> Set<eventType>

function ensureUpstream() {
  if (upstream) return;
  upstream = new EventSource('/api/stream/events');
  for (const type of WATCHED_EVENTS) {
    upstream.addEventListener(type, (ev) => broadcast(type, ev));
  }
}

function broadcast(type, ev) {
  const payload = { type: 'sse', event: type, data: ev.data, id: ev.lastEventId || null };
  for (const [port, subs] of ports) {
    if (subs.has(type) || subs.has('*')) port.postMessage(payload);
  }
}

self.addEventListener('connect', (e) => {
  const port = e.ports[0];
  ports.set(port, new Set());
  port.onmessage = (msg) => { /* subscribe / unsubscribe / ping / close */ };
  port.start();
  ensureUpstream();
});
```

**Constants**: hardcode the set of event types the server emits (see `_WATCHED_EVENTS` in `dashboard/routers/sse.py`): `running-update`, `status-update`, `test-update`, `quality-update`, `toast`.

### 2. `dashboard/static/sse-client.js`

A tiny client library, loaded globally from `base.html`. Exposes:

```javascript
window.iwSSE = {
  on(eventType, handler) { /* register handler for this tab, subscribe via worker */ },
  off(eventType, handler) { /* deregister — optional for first version but keep the API symmetrical */ },
  ready: Promise   /* resolves when the worker (or fallback EventSource) is connected */
};
```

Behavior:

- On first call to `on(...)`, instantiate the SharedWorker at `/static/sse-shared-worker.js`.
- If `typeof SharedWorker === 'undefined'` (Safari iOS, private-browsing sometimes) **OR** worker instantiation throws, fall back to `new EventSource('/api/stream/events')` on the window itself. This is the existing per-tab behavior — no regression, just no improvement.
- Multiple calls to `on(eventType, handler)` register multiple handlers locally. The client sends a single `subscribe` message per `eventType` to the worker (deduplicate).
- On `beforeunload` / `pagehide` — best-effort `port.close()`. Do NOT rely on this for correctness (mobile browsers skip `beforeunload`).
- Serialize JSON data parsing inside the handler wrapper: the worker forwards `data` as the raw string (to match `EventSource` semantics); handlers receive an object `{data: '<raw string>', lastEventId: '<id or null>'}` so they can call `JSON.parse(ev.data)` exactly as they do today.

The object shape handed to each handler MUST be compatible with the current `es.addEventListener('toast', function (e) { showToast(JSON.parse(e.data)); })` pattern so migration is mechanical.

### 3. Load `sse-client.js` in `dashboard/templates/base.html`

Add a single `<script src="{{ url_for('static', path='/sse-client.js') }}" defer></script>` in the appropriate location (follow existing static-asset conventions in `base.html`). It must be loaded on every page, before any page-specific `{% block scripts %}` content runs — the shared client must exist before pages call `iwSSE.on(...)`.

### 4. Migrate the 7 page templates

For each of the 7 templates listed in Input Files, replace the per-page `EventSource` block with `iwSSE.on(...)` calls. Example — `dashboard/templates/pages/system/running.html` currently has:

```javascript
var es = new EventSource('/api/stream/events');
es.addEventListener('running-update', function () { /* htmx.trigger(...) */ });
es.addEventListener('toast', function (e) { try { showToast(JSON.parse(e.data)); } catch (_) {} });
```

Becomes:

```javascript
iwSSE.on('running-update', function () { /* htmx.trigger(...) */ });
iwSSE.on('toast', function (e) { try { showToast(JSON.parse(e.data)); } catch (_) {} });
```

The handler signature — `function (e) { ... e.data ... }` — must be preserved exactly so the body of each handler is unchanged.

**Scope**: ONLY `new EventSource('/api/stream/events')` instances. Do NOT touch other `EventSource` usages that point to different endpoints (job streams, OSS scan streams, code index streams) — those are single-tab, finite-lifetime, and not the bug.

### 5. Self-check

After editing, run:

```bash
make lint            # includes node --check on dashboard/static/**/*.js
grep -rn "new EventSource('/api/stream/events')" dashboard/templates/
# expected: zero results
grep -rn "new EventSource(" dashboard/templates/
# expected: only job-specific stream URLs remain (docs, oss, code) — none for /api/stream/events
```

## Project Conventions

Follow `CLAUDE.md` and `dashboard/CLAUDE.md`:

- Tailwind: don't write CSS; if you need styles, use the prebuilt classes already in `styles.css`.
- Static assets: place under `dashboard/static/`.
- Dashboard JS convention: ES5-compatible / plain browser JS (existing templates use `var` and function expressions — keep that style in the new scripts to match lint expectations).
- No docker, no migrations.

## TDD Requirement

This is a client-side JS change with a cross-browser harness. Write the regression test before implementation? The test lives in S03 (Tests agent). Your S01 responsibility is to ensure:

1. The new client + worker scripts exist and are syntactically valid (`node --check`).
2. No direct `EventSource('/api/stream/events')` remains in `dashboard/templates/`.
3. Manual smoke: `./ai-core.sh dashboard restart`, open 2 tabs, open devtools Network tab, filter by `EventSource` — confirm only one underlying SSE connection exists in the SharedWorker context.

## Test Verification

Run before reporting complete:

```bash
make lint
make test-unit
```

Both must pass with zero failures. Report honestly in the result contract.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00038",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/static/sse-shared-worker.js",
    "dashboard/static/sse-client.js",
    "dashboard/templates/base.html",
    "dashboard/templates/pages/project/queue.html",
    "dashboard/templates/pages/project/batches.html",
    "dashboard/templates/pages/project/batch_detail.html",
    "dashboard/templates/pages/project/item_detail.html",
    "dashboard/templates/pages/project/tests.html",
    "dashboard/templates/pages/project/quality.html",
    "dashboard/templates/pages/system/running.html"
  ],
  "tests_passed": true,
  "test_summary": "make lint + make test-unit both green",
  "blockers": [],
  "notes": ""
}
```
