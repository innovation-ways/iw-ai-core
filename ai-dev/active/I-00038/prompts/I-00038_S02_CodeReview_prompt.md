# I-00038_S02_CodeReview_prompt

**Work Item**: I-00038 -- Dashboard hangs when multiple tabs are open (SSE connection exhaustion)
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00038/I-00038_Issue_Design.md`
- `ai-dev/active/I-00038/reports/I-00038_S01_Frontend_report.md`
- All files listed in S01's `files_changed`

## Output Files

- `ai-dev/active/I-00038/reports/I-00038_S02_CodeReview_report.md`

## Context

Per-agent review of S01. Verify the SharedWorker-based SSE client meets the design requirements and does not regress existing behavior.

## Review Checklist

### 1. SharedWorker correctness

- **Single upstream connection**: the worker instantiates `EventSource('/api/stream/events')` at most once over its lifetime (guarded; not per-port).
- **Port lifecycle**: ports are added on `connect`, removed on close; when the last port disconnects, the upstream is closed (otherwise a stale connection lingers forever on the server).
- **Event fanout**: every subscribed port receives every matching event; the payload shape matches what the current page handlers expect (`e.data` is the raw JSON string, same as `EventSource` native).
- **Subscription dedup**: sending `subscribe` twice for the same event type does not cause duplicated delivery.
- **Event types covered**: the worker listens for every type in `_WATCHED_EVENTS` from `dashboard/routers/sse.py`: `running-update`, `status-update`, `test-update`, `quality-update`, `toast`.

### 2. Client fallback correctness

- **Detection**: `typeof SharedWorker === 'undefined'` triggers the fallback.
- **Fallback parity**: the fallback opens one per-tab `EventSource('/api/stream/events')` and dispatches to the same handler set — existing behavior is preserved.
- **Handler signature**: `iwSSE.on(type, fn)` passes an object with `.data` (raw string) and `.lastEventId` to the handler, so the existing page code `JSON.parse(e.data)` works unchanged.
- **Async safety**: `iwSSE.ready` resolves after the SharedWorker port is connected (or the fallback is chosen). Subscribing before `ready` must not drop events.
- **Single instantiation**: the client lazy-instantiates the SharedWorker **once** per page; subsequent `iwSSE.on(...)` calls reuse the same instance.

### 3. Page migration completeness

Run these greps and confirm the expected results:

```bash
grep -rn "new EventSource('/api/stream/events')" dashboard/templates/
# expected: zero matches
grep -rn "EventSource('/api/stream/events')" dashboard/templates/
# expected: zero matches
grep -rn "iwSSE\\.on" dashboard/templates/pages/
# expected: at least one match in each of the 7 migrated templates
```

Every `addEventListener` for `running-update`, `status-update`, `test-update`, `quality-update`, `toast` that was previously on a per-page `EventSource` must now be on `iwSSE`. No handler body was changed in intent (only the source changed from `es` to `iwSSE`).

### 4. Out-of-scope usages untouched

Confirm these are **not** modified:

- `dashboard/templates/fragments/oss_scan_progress.html` (uses `sse-connect=` htmx attribute on a job-specific stream)
- `dashboard/templates/fragments/oss_install_modal.html`
- `dashboard/templates/fragments/docs_job_status.html`
- `dashboard/templates/fragments/code_job_status.html`
- `dashboard/templates/pages/project/oss.html`

These consume job-specific SSE endpoints that are single-tab and finite-lifetime. They are intentionally out of scope.

### 5. base.html inclusion

- `sse-client.js` is loaded on **every** page (via `base.html`) so any `{% block scripts %}` can safely reference `iwSSE`.
- Script load order: `sse-client.js` loads before any page-specific script block that calls `iwSSE.on(...)`. If `defer` is used, confirm the existing `base.html` script ordering supports it.

### 6. Conventions

- JS style matches the existing dashboard JS (`var` declarations, function expressions). No TypeScript, no module bundler.
- Both new files pass `node --check` (part of `make lint`).
- No emojis in code unless the existing style uses them (it doesn't).

### 7. Security

- The SharedWorker scope is the origin — no cross-origin exposure.
- No credentials or API keys committed.
- Worker does NOT forward arbitrary messages from tabs to the server (it only forwards upstream events downstream; the `subscribe` protocol is the only client→worker channel).

## Test Verification

Before submitting the review, run:

```bash
make lint
make test-unit
```

Report results in `tests_passed` / `test_summary`.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Breaks SSE event delivery or reintroduces the connection exhaustion | Must fix |
| HIGH | Stale upstream connection on last-tab-close; missing event type; handler signature mismatch | Must fix |
| MEDIUM (fixable) | Missing subscription dedup; inconsistent naming; missing fallback path | Should fix |
| MEDIUM (suggestion) | Better worker-termination semantics, clearer logging | Optional |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00038",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
