# I-00038 S02 Code Review Report

## What was reviewed

S01 (frontend-impl) implementation of the SharedWorker-based SSE multiplexing fix.
Files: `dashboard/static/sse-shared-worker.js`, `dashboard/static/sse-client.js`,
`dashboard/templates/base.html`, 7 migrated page templates.

---

## Checklist

### 1. SharedWorker correctness

| Item | Status | Notes |
|------|--------|-------|
| Single upstream connection | PASS | `ensureUpstream()` guarded by `if (upstream !== null) return` — created at most once |
| Port lifecycle | PASS | `close` message removes port, calls `closeUpstreamIfIdle()` — stale upstream won't linger |
| Event fanout | PASS | `broadcast()` sends `{type:'sse', event, data, id}` to all subscribed ports; closed ports caught by try/catch |
| Subscription dedup | MEDIUM | `iwSSE.on()` appends to array without checking if handler already registered. Could cause dup delivery if same fn passed twice. `off()` correctly removes all instances |
| Event types covered | PASS | `running-update`, `status-update`, `test-update`, `quality-update`, `toast` — matches `sse.py:180,190,200,210,223` |

### 2. Client fallback correctness

| Item | Status | Notes |
|------|--------|-------|
| Detection | PASS | `typeof SharedWorker !== 'undefined'` triggers fallback |
| Fallback parity | PASS | Per-tab `EventSource('/api/stream/events')` mirrors existing behavior |
| Handler signature | PASS | `{data: data.data, lastEventId: data.id}` — page code `JSON.parse(e.data)` works unchanged |
| Async safety | PASS | `_readyPromise` resolved immediately by both paths; `iwSSE.ready` is a real Promise |
| Single instantiation | PASS | `_worker`/`_fallback` module-level; subsequent `iwSSE.on()` calls reuse same instance |

### 3. Page migration completeness

All 7 templates migrated (grep confirmed `iwSSE.on` present in each):

| Template | Event Types |
|----------|-------------|
| `queue.html` | `status-update`, `toast` |
| `batches.html` | `running-update`, `status-update`, `toast` |
| `batch_detail.html` | `running-update`, `status-update`, `toast` |
| `item_detail.html` | `running-update`, `status-update`, `toast` |
| `tests.html` | `test-update`, `toast` |
| `quality.html` | `quality-update`, `toast` |
| `running.html` | `running-update`, `toast` |

No remaining `EventSource('/api/stream/events')` in templates.

### 4. Out-of-scope usages untouched

`oss_scan_progress.html`, `oss_install_modal.html`, `code_job_status.html` — all retain their job-specific `EventSource` usages (single-tab finite streams). Confirmed unchanged.

### 5. base.html inclusion

`<script src="/static/sse-client.js" defer>` at line 218, before `{% block scripts %}`. Scripts in page templates run after the deferred script loads.

### 6. Conventions

`var` declarations, function expressions, no TypeScript, no module bundler. Both files pass `node --check` with zero output.

### 7. Security

SharedWorker scope is origin-limited. No credentials/API keys committed. Worker forwards SSE events downstream only; `subscribe` is the sole client→worker protocol. No cross-origin exposure.

---

## Verdict

**PASS** — 1 MEDIUM (suggestion, not mandatory): `iwSSE.on()` has no dedup guard. Adding the same handler function twice would register it twice, causing double delivery. `off()` correctly removes all instances (by iterating in reverse), so the functional impact is limited to repeated `.on()` calls without matching `.off()`. Not a regression of existing behavior (old code had no dedup either), and not a regression since the old code would also deliver twice.

---

## Tests

```
node --check dashboard/static/sse-shared-worker.js   # exit 0
node --check dashboard/static/sse-client.js           # exit 0
make lint   # 8 pre-existing ruff errors (unrelated modules/migration files, unchanged by S01)
make test-unit  # 1385 passed, 19 warnings (pre-existing RuntimeWarning in qa_engine tests)
```

---

## Files changed

- `dashboard/static/sse-shared-worker.js` (new)
- `dashboard/static/sse-client.js` (new)
- `dashboard/templates/base.html` (modified — added sse-client.js script tag)
- `dashboard/templates/pages/project/queue.html` (migrated)
- `dashboard/templates/pages/project/batches.html` (migrated)
- `dashboard/templates/pages/project/batch_detail.html` (migrated)
- `dashboard/templates/pages/project/item_detail.html` (migrated)
- `dashboard/templates/pages/project/tests.html` (migrated)
- `dashboard/templates/pages/project/quality.html` (migrated)
- `dashboard/templates/pages/system/running.html` (migrated)

No DB migrations, no Docker state changes.