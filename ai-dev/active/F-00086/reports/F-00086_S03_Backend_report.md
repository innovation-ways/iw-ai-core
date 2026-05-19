# F-00086 S03 — Backend Step Report

**Step**: S03 (Backend)
**Agent**: backend-impl
**Status**: complete

## What was done

Implemented the runtime-agnostic chat backend layer for the multi-tab AI
Assistant Feature.

1. **`ChatRuntime` ABC** (`orch/chat/runtime_base.py`) — 13 abstract
   methods covering session lifecycle, prompting, control, permissions,
   model selection, close, subscribe, config, providers, and health. The
   `subscribe` method is declared `def` (not `async def`) so async
   generator implementations satisfy the LSP-strict mypy check.
2. **Mechanical move** — `git mv`ed the four pre-existing OpenCode
   plumbing modules into a new `orch/chat/opencode/` subpackage and
   added an `__init__.py` re-exporting the canonical names:
   - `orch/chat/opencode_runtime.py` → `orch/chat/opencode/runtime.py`
   - `orch/chat/opencode_client.py` → `orch/chat/opencode/client.py`
   - `orch/chat/relay_manager.py` → `orch/chat/opencode/relay_manager.py`
   - `orch/chat/filters.py` → `orch/chat/opencode/filters.py`
3. **`OpencodeRuntime extends ChatRuntime`** — added 12 ABC method
   implementations (the 13th, `health`, was already present). The
   session-bound methods delegate to a lazily-constructed
   `OpencodeClient`; `set_model` and `close_session` are no-ops with
   docstrings explaining why (model is routed per-prompt; tab close is a
   soft-delete that preserves the runtime session).
4. **`RelayManager` rekeyed by `tab_id`** — `get_or_create_relay(tab_id)`
   now takes a tab id, optionally resolves the OpenCode session via an
   injected `session_resolver` callable, and constructs a
   `SessionRelay(client, sid, tab_id=tab_id)` that stamps every emitted
   event (live, replayed, gap, relay.error) with the top-level
   `tab_id` field demanded by invariant #2. The `session_resolver`
   parameter defaults to None for legacy callers / existing unit tests
   that still pass the OpenCode sid directly as the relay key.
5. **`orch/chat/tab_service.py`** — module-level CRUD operating on a
   SQLAlchemy `Session`: `create_tab` (with `ALLOWED_RUNTIMES`
   allowlist + soft-cap counting), `list_tabs`, `get_tab`, `update_tab`
   (empty-body PATCH is a no-op per invariant #8), `close_tab` (soft
   delete; idempotent; preserves `opencode_session_id`), `reopen_tab`
   (idempotent), `recent_closed_tabs`, `touch_last_active`, `count_tabs`.
6. **`orch/chat/migration_helpers.py`** — `bootstrap_default_tab` seeds
   a single `Default` tab when (a) `chat_tabs` has zero rows for
   `project_id` (active OR closed — invariant #6 intent-preservation)
   AND (b) `runtime.list_sessions()` reports a session whose CWD matches
   the project repo root. Race-safe via the
   `uq_chat_tabs_default_per_project` partial unique index from S01;
   the IntegrityError branch rolls back and re-fetches the winner.
7. **`orch/chat/__init__.py`** — re-exports `ChatRuntime`,
   `OpencodeClient`, `OpencodeRuntime`, `RelayManager`, `SessionRelay`,
   `bootstrap_default_tab`, and the `tab_service` module namespace.
8. **Updated every old import path** in production code (dashboard
   router) and in the existing chat tests (8 test files) to use the new
   `orch.chat.opencode.*` paths. Verified via `grep -rn "orch.chat.opencode_runtime|orch.chat.opencode_client|orch.chat.relay_manager|orch.chat.filters" --include="*.py"`
   returning zero matches.

## Files changed

**New files**

- `orch/chat/runtime_base.py`
- `orch/chat/opencode/__init__.py`
- `orch/chat/tab_service.py`
- `orch/chat/migration_helpers.py`
- `tests/unit/chat/__init__.py`
- `tests/unit/chat/conftest.py`
- `tests/unit/chat/test_tab_service.py`

**Renamed (git mv)**

- `orch/chat/opencode_runtime.py` → `orch/chat/opencode/runtime.py`
- `orch/chat/opencode_client.py` → `orch/chat/opencode/client.py`
- `orch/chat/relay_manager.py` → `orch/chat/opencode/relay_manager.py`
- `orch/chat/filters.py` → `orch/chat/opencode/filters.py`

**Edited**

- `orch/chat/__init__.py` — re-exports updated
- `orch/chat/opencode/runtime.py` — `ChatRuntime` ABC superclass + 12
  method implementations
- `orch/chat/opencode/relay_manager.py` — rekey by `tab_id`, stamp
  `tab_id` on every emitted event
- `orch/chat/opencode/filters.py` — internal-import only update
- `dashboard/routers/chat.py` — import path update
- `tests/unit/test_chat_runtime.py` — import path updates
- `tests/unit/test_chat_client.py` — import path updates
- `tests/unit/test_chat_filters.py` — import path updates
- `tests/unit/test_chat_relay.py` — import path updates
- `tests/integration/test_chat_endpoint_session_lifecycle.py` — imports
- `tests/integration/test_chat_endpoint_permission_flow.py` — imports
- `tests/integration/test_chat_endpoint_reconnect.py` — imports
- `tests/dashboard/test_chat_panel_event_protocol.py` — imports

## TDD-RED evidence

Captured BEFORE writing `tab_service.py` / `migration_helpers.py`. The
primary failing test was the soft-cap assertion
`test_create_tab_returns_soft_cap_flag_when_count_exceeds_ten`; the
RED-run collection failed because `orch.chat.migration_helpers` did not
exist yet, which by definition means `tab_service` / `bootstrap_default_tab`
hadn't been written either:

```
ERROR tests/unit/chat/test_tab_service.py
ImportError while importing test module
'/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00086/tests/unit/chat/test_tab_service.py'.
tests/unit/chat/test_tab_service.py:26: in <module>
    from orch.chat.migration_helpers import bootstrap_default_tab
E   ModuleNotFoundError: No module named 'orch.chat.migration_helpers'
=========================== short test summary info ============================
ERROR tests/unit/chat/test_tab_service.py
=============================== 1 error in 0.15s ===============================
```

After implementing the modules, all 9 tests in the new test file pass.

## Test results

`tests/unit/chat/test_tab_service.py` (the new TDD targets):

```
collected 9 items
tests/unit/chat/test_tab_service.py::test_close_tab_is_idempotent PASSED
tests/unit/chat/test_tab_service.py::test_create_tab_persists_row_with_defaults PASSED
tests/unit/chat/test_tab_service.py::test_bootstrap_does_not_fire_when_only_closed_tabs_exist PASSED
tests/unit/chat/test_tab_service.py::test_bootstrap_is_idempotent_under_concurrent_calls PASSED
tests/unit/chat/test_tab_service.py::test_create_tab_returns_soft_cap_flag_when_count_exceeds_ten PASSED
tests/unit/chat/test_tab_service.py::test_create_tab_rejects_unknown_runtime PASSED
tests/unit/chat/test_tab_service.py::test_empty_patch_does_not_bump_updated_at PASSED
tests/unit/chat/test_tab_service.py::test_reopen_tab_restores_active_status PASSED
tests/unit/chat/test_tab_service.py::test_bootstrap_creates_default_tab_when_empty_and_session_exists PASSED
============================== 9 passed in 5.43s ===============================
```

No-regression verification of the existing chat plumbing tests after the
package move:

- `tests/dashboard/test_chat_router.py` — 34 passed
- `tests/integration/test_chat_endpoint_session_lifecycle.py` — 4 passed
- `tests/integration/test_chat_endpoint_permission_flow.py` — passed
- `tests/integration/test_chat_endpoint_reconnect.py` — passed
- `tests/unit/test_chat_runtime.py` — passed
- `tests/unit/test_chat_client.py` — passed
- `tests/unit/test_chat_relay.py` — passed
- `tests/unit/test_chat_filters.py` — passed
- `tests/dashboard/test_chat_panel_event_protocol.py` — passed

## Preflight quality gates

- `make format` — `784 files already formatted` ✅
- `make typecheck` — `Success: no issues found in 262 source files` ✅
- `make lint` — `All checks passed!` ✅

## Notable design choices / observations

1. **Lazy `OpencodeClient` inside `OpencodeRuntime`** — the ABC methods
   delegate to a chat client built on first invocation (using the
   runtime's own base URL + password). This preserves the existing test
   patches that mock `httpx.AsyncClient` only at the runtime module
   level, and keeps `start()`/`stop()` unchanged.
2. **Optional `session_resolver` on `RelayManager`** — the rekey from
   sid to tab_id is backwards-compatible. When `session_resolver` is
   None (the default), the manager treats the argument as the runtime
   session id directly — exactly the pre-F-00086 contract — so the
   existing `test_chat_relay.py` unit tests and integration tests that
   pre-date the tab-scoped API surface continue to pass. S06 (API
   step) will wire the production resolver via `tab_service.get_tab`.
3. **`subscribe` declared `def` on the ABC** — `async def foo(): yield`
   is typed by mypy as `Coroutine[..., AsyncIterator]`, not
   `AsyncIterator`. Declaring `subscribe` as a plain `def` returning
   `AsyncIterator` lets concrete implementations be async generators
   without the LSP override error.
4. **Concurrent-bootstrap test uses independent connections from the
   `db_engine` clone** — the project's `db_session_factory` pins all
   sessions to a single shared connection (so test fixtures stay
   consistent), which makes it unable to model a real race. The test
   uses `sessionmaker(bind=db_engine)` to open two truly independent
   connections, demonstrating that the partial unique index serialises
   the inserts.
5. **`bootstrap_default_tab` uses `asyncio.run`** — `tab_service` is
   sync; the runtime is async. The helper is sync to match the rest of
   the service surface, and raises loudly if called from inside a
   running event loop (which shouldn't happen — dashboard request
   handlers can `await runtime.list_sessions()` directly and pass the
   list in, but the current call site mode is from sync code).
