# I-00038: Dashboard hangs when multiple tabs are open (SSE connection exhaustion)

**Type**: Issue
**Severity**: High
**Created**: 2026-04-24
**Reported By**: sergiog (live debugging session)
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. The orchestration database, daemon, dashboard, and any long-lived infrastructure containers are outside your scope. Read-only introspection is allowed (`docker ps`, `docker inspect`, `docker logs`). Invoke `./ai-core.sh` or `make` targets instead. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No alembic mutation commands (`upgrade`, `downgrade`, `stamp`) against the live DB (port 5433). Agents only write migration files; the daemon applies them. Not applicable to this incident — no Database step.

## Description

The dashboard appears to hang after a user opens several tabs. Page clicks, htmx fragment loads, and image requests queue for tens of seconds before responding. The server itself is healthy (responds in single-digit milliseconds to curl) — the bottleneck is the browser's per-origin HTTP/1.1 connection limit (~6). Every dashboard page opens its own long-lived `EventSource('/api/stream/events')`, so after ~6 tabs every slot is held by SSE and new requests queue.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. The SSE stream is defined in `dashboard/routers/sse.py`; client consumers are in `dashboard/templates/pages/**/*.html`.

## Browser Evidence

**Status**: deferred — "hang" symptom requires 6+ concurrent tabs against a live stack. Reproduction was confirmed live on 2026-04-24 via server-side diagnostics:

```text
$ ss -tn state established '( sport = :9900 )' | wc -l
12
$ ss -tn state established '( sport = :9900 )' | awk 'NR>1 {split($5,a,":"); print a[1]}' | sort | uniq -c | sort -rn
      6 192.168.0.122
      5 127.0.0.1
```

The `192.168.0.122` client was the user's browser sitting at exactly the HTTP/1.1 per-origin cap, with the dashboard responding in 9 ms to curl from localhost — confirming the bottleneck was client-side connection exhaustion, not server load.

Post-fix browser verification (S11) will orchestrate 8 Playwright browser contexts and assert the dashboard's connection count does not scale with tab count (see **Browser Verification Test** below).

## Steps to Reproduce

1. Start the stack: `./ai-core.sh start`.
2. Open http://localhost:9900/ in a browser.
3. Open 5–7 additional tabs pointing to different pages that open an SSE connection:
   - `/project/{id}/` (queue)
   - `/project/{id}/batches`
   - `/project/{id}/batch/{BATCH-ID}`
   - `/project/{id}/item/{ITEM-ID}`
   - `/project/{id}/tests`
   - `/project/{id}/quality`
   - `/system/running`
4. In any tab, click a link that normally loads in <100 ms (e.g. navigate to another item).

**Expected**: The new page loads immediately regardless of how many other tabs are open. Any new page continues to receive SSE events.

**Actual**: The new page hangs for tens of seconds. Waiting long enough (until one of the existing SSE connections times out or the user closes a tab) unblocks the queue. Closing tabs restores responsiveness.

## Browser Verification Script

Because the symptom requires 6+ concurrent tabs, a single-shell `playwright-cli` snapshot is not sufficient. The Browser Verification step (S11) uses the Playwright harness under `tests/dashboard/browser/` and the guidance in `QVBrowser_Prompt_Template.md` to orchestrate multiple browser contexts against `$IW_BROWSER_BASE_URL`. See S11 prompt for the concrete commands.

## Root Cause Analysis

Each dashboard page template instantiates its own `EventSource('/api/stream/events')`:

- `dashboard/templates/pages/project/queue.html:199`
- `dashboard/templates/pages/project/batches.html:200`
- `dashboard/templates/pages/project/batch_detail.html:290`
- `dashboard/templates/pages/project/item_detail.html:129`
- `dashboard/templates/pages/project/tests.html:81`
- `dashboard/templates/pages/project/quality.html:76`
- `dashboard/templates/pages/system/running.html:219`

The server-side stream (`dashboard/routers/sse.py:161 _event_generator`) is a long-lived async generator — each connection holds one slot for the lifetime of the tab (only closed on client disconnect or polling failure). HTTP/1.1 browsers cap concurrent connections per origin at ~6 (Chrome/Firefox defaults). Seven page templates × one tab each already saturates the cap; any further request (page navigation, htmx fragment fetch, static asset) queues until an SSE socket frees.

There is no existing primitive in the repo that shares a single SSE connection across tabs. The fix introduces one.

## Affected Components

| Component | Impact |
|-----------|--------|
| `dashboard/static/` | New files: `sse-shared-worker.js`, `sse-client.js` |
| `dashboard/templates/base.html` | Load `sse-client.js` globally |
| `dashboard/templates/pages/project/queue.html` | Replace direct `EventSource` with `iwSSE` client |
| `dashboard/templates/pages/project/batches.html` | Replace direct `EventSource` |
| `dashboard/templates/pages/project/batch_detail.html` | Replace direct `EventSource` |
| `dashboard/templates/pages/project/item_detail.html` | Replace direct `EventSource` |
| `dashboard/templates/pages/project/tests.html` | Replace direct `EventSource` |
| `dashboard/templates/pages/project/quality.html` | Replace direct `EventSource` |
| `dashboard/templates/pages/system/running.html` | Replace direct `EventSource` |
| `dashboard/routers/sse.py` | No change. Server-side unchanged. |

Other `EventSource` usages in the codebase are single-tab job streams (code indexing, doc generation, OSS scan) with finite lifetimes — they are **out of scope** and are left untouched. The shared client is opt-in for the `/api/stream/events` global stream only.

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | Implement `sse-shared-worker.js`, `sse-client.js`, load client in `base.html`, migrate 7 page templates | — |
| S02 | CodeReview | Review S01 | — |
| S03 | Tests | Regression test: multi-tab connection count; unit tests for the client-side dispatch + fallback | — |
| S04 | CodeReview | Review S03 | — |
| S05 | CodeReview_Final | Cross-layer consistency, completeness vs design, no stray `EventSource('/api/stream/events')` remaining | — |
| S06 | QV: lint | `make lint` (includes `node --check` on all dashboard JS) | — |
| S07 | QV: format | `uv run ruff format --check .` | — |
| S08 | QV: typecheck | `make typecheck` | — |
| S09 | QV: unit-tests | `make test-unit` | — |
| S10 | QV: integration-tests | `make test-integration` (timeout 900) | — |
| S11 | QV: browser | Playwright: open 8 tabs, assert connection count ≤ 2 server-side, assert every tab receives a toast emitted by the daemon | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no Database step.

### Code Changes

- **Files to create**: `dashboard/static/sse-shared-worker.js`, `dashboard/static/sse-client.js`
- **Files to modify**: `dashboard/templates/base.html` + 7 page templates (list above)
- **Nature of change**: Introduce a SharedWorker-backed client that multiplexes one upstream SSE connection across tabs; migrate page templates off direct `EventSource` for `/api/stream/events`.

## File Manifest

All files for this work item live under `ai-dev/active/I-00038/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00038_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00038_S01_Frontend_prompt.md` | Prompt | S01 Frontend — implement shared SSE client + page migration |
| `prompts/I-00038_S02_CodeReview_prompt.md` | Prompt | S02 Code review of S01 |
| `prompts/I-00038_S03_Tests_prompt.md` | Prompt | S03 Regression + unit tests |
| `prompts/I-00038_S04_CodeReview_prompt.md` | Prompt | S04 Code review of S03 |
| `prompts/I-00038_S05_CodeReview_Final_prompt.md` | Prompt | S05 Final cross-layer review |
| `prompts/I-00038_S11_BrowserVerification_prompt.md` | Prompt | S11 Browser verification |

Reports are created during execution in `ai-dev/active/I-00038/reports/`.

## Test to Reproduce

### Reproduction test (Python + Playwright harness)

The reproduction test opens N browser contexts against a Uvicorn-hosted dashboard and asserts server-side connection count. Against the pre-fix code, opening 7 browser contexts produces 7+ established TCP connections to port 9900 (each holding an SSE socket). Against the fixed code, with SharedWorker, the count is ≤ 2 regardless of N. A parallel control variant without SharedWorker support (Playwright `--browser-arg=--disable-features=SharedWorker` or similar) documents the fallback retains current behavior.

```python
# tests/dashboard/browser/test_sse_shared_worker.py
import subprocess
import pytest
pytestmark = pytest.mark.browser


def _count_sse_connections(port: int) -> int:
    """Count established TCP connections on ``port`` by calling ss(8)."""
    out = subprocess.check_output(
        ["ss", "-tn", "state", "established", f"( sport = :{port} )"],
        text=True,
    )
    # Header line + one per connection. Drop header, drop any loopback self-connections.
    return max(0, len(out.strip().splitlines()) - 1)


def test_multi_tab_does_not_exhaust_connection_budget(dashboard_server, playwright_session):
    """With SharedWorker, N tabs ≠ N SSE connections.

    This test FAILS on pre-fix code (per-tab EventSource) and PASSES on fixed code.
    """
    # ... open 8 tabs, each hitting a page that uses /api/stream/events
    # ... assert _count_sse_connections(port) <= 2 (worker + fallback)
```

Exact harness details are in the S03 prompt. The test leverages existing fixtures in `tests/dashboard/browser/conftest.py`.

### Semantic correctness of the test

**Important** — the test must assert **connection count does not scale with tab count**, not merely "SSE works". Checking "one tab receives events" passes on both the broken and fixed code and does not catch the regression. The assertion is a specific numeric bound (`<= 2`), not shape-only.

## Browser Verification Test (S11)

Playwright driven by `playwright-cli` will:

1. Open 8 contexts to 8 different dashboard pages.
2. In each context, interact (click a nav link) and verify the page responds in under 1 s.
3. Via a server-side probe, assert the number of established `/api/stream/events` connections is ≤ 2.
4. Trigger a toast (e.g. via `iw daemon reload` or a test-only event emitter) and assert all 8 tabs display it.

Full V1..V5 in the S11 prompt.

## Acceptance Criteria

### AC1: Bug is fixed — multiple tabs remain responsive

```
Given the dashboard is running
And the user has 8 tabs open, each pointing at different pages that subscribe to /api/stream/events
When the user clicks a nav link in any of those tabs
Then the new page loads in under 1 second
And all other tabs continue to receive SSE events
```

### AC2: Connection count does not scale with tab count

```
Given the browser supports SharedWorker
When N tabs are open on the dashboard
Then the server-side count of established /api/stream/events connections from that browser is 1
```

### AC3: Fallback preserves behavior in unsupported environments

```
Given the browser does NOT support SharedWorker (fallback path)
When the user opens tabs on the dashboard
Then each tab opens its own EventSource (existing behavior)
And no regression in event delivery occurs
```

### AC4: All existing SSE event types are delivered to every tab

```
Given multiple tabs are open
When the daemon emits a running-update / status-update / test-update / quality-update / toast event
Then every tab that registered a handler for that event receives it
And in the same order the daemon emitted them
```

### AC5: Regression test exists

```
Given the fix is applied
When make test-integration runs the browser suite
Then tests/dashboard/browser/test_sse_shared_worker.py passes
And asserts connection count does not scale with tab count
```

### AC6: No direct EventSource('/api/stream/events') remains

```
Given the fix is applied
When ripgrep searches dashboard/templates for EventSource('/api/stream/events')
Then zero matches are returned
(The shared client is the only subscriber to that endpoint.)
```

### AC7: Page-local EventSource usages for other endpoints are untouched

```
Given the fix is applied
When ripgrep searches dashboard/templates for "new EventSource"
Then matches for job-specific streams remain
(e.g. /api/docs/jobs/{id}/stream, OSS scan streams, code index streams)
```

## Regression Prevention

- **Lint rule** (dashboard JS): new JS is linted by `make lint` (`node --check`).
- **Architecture grep** in `CodeReview_Final`: grep for `new EventSource\(\s*['\"]/api/stream/events` in `dashboard/templates/` — must return zero hits. Codify this check in the S05 prompt.
- **Regression test**: `test_multi_tab_does_not_exhaust_connection_budget` (S03) lives in `tests/dashboard/browser/` and runs as part of `make test-integration` / `make check`.
- **Client hardening**: the new `iwSSE` API is the only sanctioned consumer of the global SSE stream. Page templates that need generic updates go through `iwSSE.on(...)`.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Reproducing test**: `test_multi_tab_does_not_exhaust_connection_budget` — fails on pre-fix (7 connections from 7 tabs), passes after fix (1 connection).
- **Unit tests**: Pure JS unit tests are difficult in this project (no node test framework configured). Coverage is delivered via:
  - `node --check` for syntax (already run by `make lint`).
  - Template rendering tests (`tests/dashboard/`) that assert `sse-client.js` is included in `base.html` and that specific pages no longer emit `new EventSource('/api/stream/events')`.
- **Integration tests**: The browser harness test above exercises the full stack (Uvicorn + browser + shared worker).

## Notes

- **Out of scope**: server-side last-event-id resumption. The current `sse.py` does not honor the `Last-Event-ID` header; events lost during a reconnect window are the existing behavior. Fixing that is a separate work item.
- **Out of scope**: non-global SSE endpoints (job-specific streams under `/api/docs/jobs/{id}/stream`, OSS scan streams, etc.). They have single-tab, finite-lifetime connections and do not contribute to the exhaustion.
- **Security**: SharedWorker scope is the origin — cross-tab communication is safe by default and does not expose data to other origins. The worker only forwards server-sent events the tabs already subscribe to individually.
- **Browser support**: SharedWorker is supported in all major desktop browsers. It is not supported in Safari on iOS (fallback path preserves current behavior). The fallback is an explicit documented path, not a silent regression.
