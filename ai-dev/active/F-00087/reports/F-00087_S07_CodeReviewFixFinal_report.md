# F-00087 — S07 Code Review Fix (Final) Report

**Fix Cycle**: 1 of 5
**Review That Triggered Fix**: S06 (Final Cross-Agent Review)
**Status**: Completed — all CRITICAL/HIGH/LOW findings addressed, all targeted tests pass.

---

## Summary

The S06 final cross-agent review identified that S01's `get_runtime_for_tab()`
helper was created in `orch/chat/__init__.py` but never wired into the
dashboard router (`dashboard/routers/chat.py`). Every per-tab endpoint was
still OpenCode-only:

- `POST   /api/chat/tabs` — gated on OpenCode health, called `OpencodeClient.create_session()`
- `GET    /api/chat/tabs/{id}` — fetched session/messages via OpenCode
- `POST   /api/chat/tabs/{id}/prompt` — sent to OpenCode
- `POST   /api/chat/tabs/{id}/abort` — sent to OpenCode
- `POST   /api/chat/tabs/{id}/permissions/{rid}` — replied via OpenCode (AC3 broken at HTTP layer)
- `GET    /api/chat/tabs/{id}/stream` — relied on `RelayManager` which is OpenCode-only

S07 wired Pi runtime dispatch into all six endpoints and added a router-level
integration test suite (`tests/dashboard/test_chat_router_pi.py`) that closes
the HIGH finding by exercising the HTTP API path for Pi tabs.

---

## Findings Addressed

### CRITICAL #1 — Missing router-level Pi dispatch
**Status**: fixed
**Files changed**:
- `dashboard/routers/chat.py`

Implemented per-tab runtime dispatch across all six affected endpoints:

- **`create_tab`** (POST `/api/chat/tabs`):
  - New early branch on `body.runtime == "pi"`.
  - Resolves Pi runtime from `request.app.state.pi_runtime`.
  - Independent Pi health check (calls `pi_runtime.health()`).
  - New helper `_resolve_pi_model_config(db, project_key)` resolves Pi models
    from `agent_runtime_options` table (mirrors get_config Pi branch), applies
    the project's `ai_assistant.models` allowlist intersection.
  - Calls `pi_runtime.create_session()` instead of `OpencodeClient.create_session()`.
  - Pi session id is stored in `chat_tabs.opencode_session_id` (column reused
    as the per-runtime session id; same as OpenCode pattern).

- **`get_tab`** (GET `/api/chat/tabs/{id}`):
  - Reads tab from DB first, branches on `tab.runtime`.
  - Pi path: calls `pi_runtime.get_session(sid)` + `pi_runtime.get_messages(sid)`.
  - Pi health check returns 503 with `"Pi runtime unavailable"` payload when
    the binary is missing.

- **`send_prompt`** (POST `/api/chat/tabs/{id}/prompt`):
  - Reads tab from DB first, branches on `tab.runtime`.
  - Pi path: `pi_runtime.prompt(sid, text, model=..., system=...)`.
  - Context-chip system arg is threaded identically for both runtimes.

- **`abort_tab`** (POST `/api/chat/tabs/{id}/abort`):
  - Reads tab from DB first, branches on `tab.runtime`.
  - Pi path: `pi_runtime.abort(sid)`.

- **`reply_permission`** (POST `/api/chat/tabs/{id}/permissions/{rid}`) — **AC3 fix**:
  - Reads tab from DB first, branches on `tab.runtime`.
  - Pi path: `pi_runtime.reply_permission(sid, rid, response, remember=...)`.
  - Closes the HTTP-layer half of the approval round-trip (Python-layer was
    already correct per S06 trace).

- **`stream_tab`** (GET `/api/chat/tabs/{id}/stream`):
  - Reads tab from DB first, branches on `tab.runtime`.
  - Pi path: `_pi_subscribe_with_tab_id(pi_runtime, sid, tab_id)` adapts
    `PiRuntime.subscribe()` to the SSE generator, stamping `"tab_id"` onto
    every event (matching the RelayManager invariant for OpenCode tabs).
  - No `Last-Event-ID` ring-buffer replay for Pi in v1 (Pi has its own
    `--session` resume semantics).

- **New helper `_resolve_pi_runtime_or_503(request)`**: factored out the
  Pi-runtime + health-check + 503 short-circuit so the per-tab endpoints stay
  readable.

Dispatch decision is always based on `tab.runtime` for existing tabs and
`body.runtime` for `create_tab`. No reliance on FastAPI's
`Depends(_get_runtime)` for Pi tabs (that dependency is OpenCode-specific
and cannot dispatch per-tab in a clean way).

### CRITICAL #2 — Stale create_tab docstring
**Status**: fixed
**Files changed**: `dashboard/routers/chat.py`

The docstring now accurately describes the runtime allowlist (`{"opencode",
"pi"}`) and that Pi tabs route to `PiRuntime`. (Replaced as part of the
CRITICAL #1 refactor.)

### HIGH #3 — Missing router-level integration tests for Pi tabs
**Status**: fixed
**Files changed**: `tests/dashboard/test_chat_router_pi.py` (new file)

Added a router-level test suite using FastAPI `TestClient` with the
`db_session` testcontainer fixture (same pattern as `test_chat_router.py`).
Ten tests covering:

1. `test_create_pi_tab_calls_pi_runtime_not_opencode` — POST with runtime=pi
   creates a session via PiRuntime, NOT OpencodeClient.
2. `test_create_pi_tab_rejects_non_pi_model` — Pi tab with an OpenCode-only
   model returns 400.
3. `test_create_pi_tab_503_when_pi_runtime_unhealthy` — Pi binary missing →
   503 with `"Pi runtime unavailable"` payload.
4. `test_prompt_on_pi_tab_calls_pi_runtime` — POST /prompt on a Pi tab
   dispatches to PiRuntime.prompt, not OpencodeClient.prompt.
5. `test_prompt_threads_context_chip_for_pi_tab` — Context-chip `system`
   arg flows through identically for Pi.
6. `test_permission_approve_on_pi_tab_calls_pi_runtime` — **AC3 fix
   regression guard** — POST /permissions/{rid} dispatches to
   PiRuntime.reply_permission.
7. `test_permission_deny_on_pi_tab_passes_through` — Deny response routes
   correctly with `remember=True` forwarded.
8. `test_abort_pi_tab_calls_pi_runtime` — POST /abort dispatches to
   PiRuntime.abort.
9. `test_get_pi_tab_calls_pi_runtime` — GET /tabs/{id} fetches via
   PiRuntime.get_session + PiRuntime.get_messages.
10. `test_opencode_tab_still_routes_to_opencode` — **Cross-runtime
    isolation guard** — OpenCode tabs MUST keep routing to OpencodeClient
    when both runtimes are wired.

Each test asserts BOTH (a) the correct runtime gets the call AND (b) the
other runtime does NOT get the call. The `_seed_pi_models` helper is
idempotent so it co-exists with the CR-00062 migration seed.

### MEDIUM #4 — `_get_runtime()` hardcodes opencode_runtime
**Status**: partially_fixed (per S06 acceptance — the helper itself is kept
for OpenCode-only Depends() chains; per-tab endpoints now resolve Pi runtime
inside each handler via `_resolve_pi_runtime_or_503`).

The cleaner long-term refactor (Pi-aware Depends() chain) is deferred to a
follow-up. The current pattern (look up tab → branch on runtime → resolve
appropriate runtime) is simple, explicit, and unit-tested.

### LOW #5 — Inline `from sqlalchemy import select` with `noqa: PLC0415`
**Status**: fixed
**Files changed**: `dashboard/routers/chat.py`

Lifted `from sqlalchemy import select` to the module-level imports
alongside the other sqlalchemy imports. The inline `noqa` was removed.

### LOW #6 — pi_rpc_client.py docstring overstates SIGTERM behaviour
**Status**: fixed
**Files changed**: `orch/chat/pi/pi_rpc_client.py`

Updated the module docstring to accurately describe that
`start_new_session=True` puts the subprocess in its own group but
`close()` sends signals to the leader only. References F-00087 §Out of
Scope: "Crash-recovery reaper for orphaned subprocesses" as the tracked
follow-up.

---

## Existing Tests Updated

Four tests in `tests/dashboard/test_chat_router.py` (TestRuntimeUnavailable)
previously expected 503 for non-existent tabs. With the new dispatch order
(tab lookup BEFORE runtime health check, required for per-tab runtime
dispatch), missing tabs return 404. Tests were updated to create a real
OpenCode tab first to exercise the health-gate-after-lookup path:

- `test_runtime_none_stream_returns_503`
- `test_runtime_none_prompt_returns_503`
- `test_runtime_none_abort_returns_503`
- `test_runtime_none_permissions_returns_503`

The existing `test_get_session_runtime_none_returns_503` already documented
this pattern (404-before-503 for missing tabs) — the four updated tests
align with it.

---

## Files Changed

- `dashboard/routers/chat.py` — Pi dispatch wiring across 6 endpoints +
  `_resolve_pi_model_config` + `_resolve_pi_runtime_or_503` +
  `_pi_subscribe_with_tab_id` helpers + lifted sqlalchemy import.
- `orch/chat/pi/pi_rpc_client.py` — docstring correction.
- `tests/dashboard/test_chat_router_pi.py` — **new file** — 10 router-level
  Pi dispatch tests.
- `tests/dashboard/test_chat_router.py` — 4 existing tests updated to match
  the new tab-lookup-before-health-gate dispatch order.

---

## Test Results

```
uv run pytest tests/unit/chat/test_pi_*.py tests/unit/chat/test_sync_agents_extensions.py tests/unit/chat/test_tab_service_allowlist.py
=> 66 passed in 7.55s

uv run pytest tests/integration/test_chat_pi_*.py
=> 13 passed in 3.82s

uv run pytest tests/dashboard/test_chat_router.py tests/dashboard/test_chat_router_pi.py
=> 55 passed in 20.27s   (45 existing OpenCode + 10 new Pi)

make lint           => All checks passed!
make type-check     => Success: no issues found in 267 source files
make format-check   => 808 files already formatted
```

Total: 134 tests, 0 failures.

---

## Fix Result JSON

```json
{
  "step": "S07",
  "agent": "code-review-fix-final-impl",
  "work_item": "F-00087",
  "fix_cycle": 1,
  "review_step": "S06",
  "findings_addressed": [
    {
      "finding_number": 1,
      "severity": "CRITICAL",
      "status": "fixed",
      "files_changed": [
        "dashboard/routers/chat.py"
      ],
      "description": "Wired Pi runtime dispatch into create_tab, get_tab, send_prompt, abort_tab, reply_permission, and stream_tab. Pi tabs now route to PiRuntime via request.app.state.pi_runtime; OpenCode tabs continue routing through OpencodeClient/RelayManager unchanged. AC3 approval HTTP round-trip is fixed."
    },
    {
      "finding_number": 2,
      "severity": "CRITICAL",
      "status": "fixed",
      "files_changed": [
        "dashboard/routers/chat.py"
      ],
      "description": "create_tab docstring updated to describe the actual runtime allowlist {opencode, pi} and the per-runtime dispatch behaviour."
    },
    {
      "finding_number": 3,
      "severity": "HIGH",
      "status": "fixed",
      "files_changed": [
        "tests/dashboard/test_chat_router_pi.py",
        "tests/dashboard/test_chat_router.py"
      ],
      "description": "Added 10 router-level integration tests for Pi tabs (POST tabs, prompt, abort, permissions, get_tab) using FastAPI TestClient + testcontainer db_session. Each test asserts the correct runtime receives the call AND the other runtime does NOT (cross-runtime isolation guard). Also updated 4 existing OpenCode tests to match the new tab-lookup-before-health-gate dispatch order."
    },
    {
      "finding_number": 4,
      "severity": "MEDIUM_FIXABLE",
      "status": "partially_fixed",
      "files_changed": [
        "dashboard/routers/chat.py"
      ],
      "description": "_get_runtime() Depends() chain is preserved as the OpenCode-only health gate. Per-tab endpoints now resolve PiRuntime inside the handler via the new _resolve_pi_runtime_or_503 helper after the DB tab lookup. The cleaner Pi-aware Depends() refactor is deferred to a follow-up; the current pattern is explicit and fully tested."
    },
    {
      "finding_number": 5,
      "severity": "LOW",
      "status": "fixed",
      "files_changed": [
        "dashboard/routers/chat.py"
      ],
      "description": "Lifted 'from sqlalchemy import select' from inline-with-noqa in get_config to the module-level import block."
    },
    {
      "finding_number": 6,
      "severity": "LOW",
      "status": "fixed",
      "files_changed": [
        "orch/chat/pi/pi_rpc_client.py"
      ],
      "description": "Updated the module docstring to accurately describe what close() does (leader-only SIGTERM/SIGKILL) and reference the F-00087 §Out of Scope process-group reaper as the tracked follow-up."
    }
  ],
  "missing_requirements_implemented": [
    "Router dispatch to PiRuntime for create_tab, send_prompt, abort_tab, reply_permission, get_tab, stream_tab endpoints",
    "Router-level integration tests for Pi tab HTTP API paths"
  ],
  "findings_skipped": [],
  "tests_passed": true,
  "test_summary": "Targeted: 66 unit Pi tests + 13 integration Pi tests + 55 dashboard router tests (45 existing OpenCode + 10 new Pi) = 134 total, 0 failures. make lint, make type-check, make format-check all green.",
  "notes": "All CRITICAL and HIGH S06 findings are fixed end-to-end. The Python-layer round-trip was already correct in S01-S05; S07 closes the HTTP-layer gap by wiring six router endpoints + adding regression tests. AC3 approval flow now works end-to-end through the HTTP API."
}
```
