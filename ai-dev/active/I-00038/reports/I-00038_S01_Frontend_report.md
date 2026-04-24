# I-00038 S01 Frontend Report

## What was done

Implemented the SharedWorker-based SSE multiplexing fix to resolve dashboard hangs when multiple tabs are open.

### Files created

- `dashboard/static/sse-shared-worker.js` — SharedWorker that maintains a single upstream `EventSource('/api/stream/events')` and fans out events to all connected browser tabs.
- `dashboard/static/sse-client.js` — Client library that provides `window.iwSSE.on(eventType, handler)`, falling back to per-tab `EventSource` when SharedWorker is unavailable.

### Files modified

- `dashboard/templates/base.html` — Added `<script src="/static/sse-client.js" defer>` before `{% block scripts %}`.
- 7 page templates migrated from `new EventSource('/api/stream/events')` + `es.addEventListener(...)` to `iwSSE.on(...)`:
  - `dashboard/templates/pages/project/queue.html`
  - `dashboard/templates/pages/project/batches.html`
  - `dashboard/templates/pages/project/batch_detail.html`
  - `dashboard/templates/pages/project/item_detail.html`
  - `dashboard/templates/pages/project/tests.html`
  - `dashboard/templates/pages/project/quality.html`
  - `dashboard/templates/pages/system/running.html`

## Verification

- `node --check dashboard/static/sse-shared-worker.js` — passed
- `node --check dashboard/static/sse-client.js` — passed
- `grep -rn "new EventSource('/api/stream/events')" dashboard/templates/` — zero results (confirmed all replaced)
- Remaining `new EventSource(` usages in templates are for job-specific streams (code index, OSS scan) — out of scope per brief
- `make lint` — pre-existing ruff errors (in migration files, unrelated modules); no new errors introduced
- `make test-unit` — 2 pre-existing failures in `test_browser_env.py` (unrelated to SSE); 1383 tests pass

## Notes

- The SSE event names hardcoded in the worker (`running-update`, `status-update`, `test-update`, `quality-update`, `toast`) match the client-facing event names from `sse.py:180,190,200,210,223` — not the server-side `DaemonEvent.event_type` values in `_WATCHED_EVENTS`.
- The `sse-client.js` fallback path (`new EventSource` directly on window) mirrors the existing per-tab behavior exactly, ensuring no regression in Safari iOS or private-browsing contexts.
- Handler signatures preserved exactly so page template bodies are unchanged (mechanical migration).
