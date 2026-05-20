# F-00087 — Step S05 (Tests) Report

**Step**: S05 · **Agent**: `tests-impl` · **Date**: 2026-05-19

## Summary

Wrote and verified the dedicated test coverage for F-00087 (Pi runtime + per-tab
runtime selection). Each Invariant from the design document maps to at least one
named test. All 79 new tests pass under deterministic and random ordering (seed
42424 verified).

## Files Changed

### Unit (8 files)

- `tests/unit/chat/test_pi_jsonl_reader.py` — 9 tests covering invariants #1
  (no built-in line iterators, verified via AST walk) and #2 (Unicode
  separators inside JSON strings do not split records), plus partial-record
  buffering, CRLF stripping, empty stream, empty lines, multi-record chunk,
  and trailing-partial-at-EOF contract pinning.
- `tests/unit/chat/test_pi_rpc_client.py` — 10 tests covering JSON+LF stdin
  writes, JSONL stdout iteration, FIFO request-response correlation,
  `reply_extension_ui` payload shape (approve + deny), idempotent `close()`,
  SIGTERM→SIGKILL escalation, and `last_activity` updates on send and
  receive.
- `tests/unit/chat/test_pi_runtime_lru_eviction.py` — 4 tests for invariant
  #4: LRU eviction triggers at `MAX_PI_TABS` (default 6, env-var
  configurable via `IW_CORE_MAX_PI_TABS`), evicted tabs preserve metadata
  for respawn.
- `tests/unit/chat/test_pi_runtime_idle_reaper.py` — 5 tests for invariant
  #5: idle reaper culls clients past `IDLE_TIMEOUT_SECONDS`, leaves
  recently-active clients untouched, honours
  `IW_CORE_PI_IDLE_TIMEOUT` override, and the reaper task is cancelled
  cleanly on runtime shutdown.
- `tests/unit/chat/test_pi_runtime_abc_compliance.py` — 3 tests for invariant
  #3: `PiRuntime.__abstractmethods__` is empty (constructible), every
  `ChatRuntime` abstract method has a compatible implementation.
- `tests/unit/chat/test_pi_event_normalization.py` — 21 tests for invariant
  #6: every Pi event type from the §Scope mapping table is translated
  correctly (message_update → message.part.added, tool_execution_* events,
  agent_start/end → session.start/idle, `extension_ui_request` with the
  `iw-chat-approvals.*` namespace → `permission.asked`, other id namespaces
  pass through as `extension.ui_request`, `extension_error` →
  `session.error`, unknown events pass through; normalizer never adds
  `tab_id`).
- `tests/unit/chat/test_sync_agents_extensions.py` — 7 tests for invariant
  #8 / AC7: extension subdirs copied into `<project>/.pi/extensions/`,
  `pi_extensions_synced` counter increments, sync is idempotent, dangling
  symlinks logged but don't break other extensions, existing
  `pi_agents_synced` counter still works alongside the new one.
- `tests/unit/chat/test_tab_service_allowlist.py` — 7 tests covering
  invariant #7 (runtime `"pi"` is allowed, OpenCode still allowed,
  unrecognised runtime rejected, error message format preserved).

### Integration (3 files + 2 stubs)

- `tests/integration/test_chat_pi_mixed_tabs_independence.py` — 4 tests for
  AC1: two Pi tabs use distinct subprocesses; aborting one Pi tab does not
  affect others; closing one Pi tab does not close others.
- `tests/integration/test_chat_pi_approval_flow.py` — 3 tests for AC3:
  `extension_ui_request` with the `iw-chat-approvals.*` id namespace
  surfaces as a `permission.asked` event with the enriched payload;
  approve response sends `value:true` and the stub proceeds with
  `tool.execution.end`; deny response sends `value:false` and the stub
  returns `denied`.
- `tests/integration/test_chat_pi_lifecycle.py` — 6 tests: lazy spawn on
  first prompt, idle-reaper kill + reactivate respawn (with
  `IW_CORE_PI_IDLE_TIMEOUT=1`), LRU eviction at the Nth tab (with
  `IW_CORE_MAX_PI_TABS=3`), Pi binary missing raises
  `RuntimeError("pi binary not found on PATH")`, `health()` returns
  False when missing and True when stub present.
- `tests/integration/stubs/pi` — 3-line bash wrapper that exec's the
  Python stub.
- `tests/integration/stubs/_pi_stub.py` — Python stub Pi RPC binary. Runs
  prompt handlers in worker threads so the stub can answer
  `extension_ui_response` while a prompt is mid-flight; stdout writes are
  serialised with a lock.

## Tests Results

```
$ uv run pytest tests/unit/chat/test_pi_*.py \
    tests/unit/chat/test_sync_agents_extensions.py \
    tests/unit/chat/test_tab_service_allowlist.py \
    tests/integration/test_chat_pi_*.py -v --no-cov
============================== 79 passed in 11.23s ==============================
```

Verified green under `pytest-randomly --randomly-seed=42424` and the
deterministic `-p no:randomly` order.

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | 807 files already formatted |
| `make typecheck` | `Success: no issues found in 267 source files` |
| `make lint` | `All checks passed!` |

## Observations & Issues Resolved

- **JSONL reader trailing-partial contract**: S01's implementation flushes any
  remaining buffer at EOF (yields the partial bytes as the last record). The
  test now pins this contract by asserting on the raw bytes of the partial
  (the JSON is incomplete by design — callers handle `JSONDecodeError`).
- **PiRpcClient pump race**: The fan-out queue in `PiRpcClient.events()` is
  registered the first time the iterator is awaited. Tests must subscribe
  before sending the prompt (or before feeding stdout bytes), otherwise
  events fan out to an empty queue list and are dropped. The
  `_subscribe_with_normalization` helper in the approval-flow tests
  pre-spawns the client and gives the iterator a slice to register its
  queue before any prompt is sent.
- **Stub Pi deadlock**: The original stub was single-threaded — when a
  prompt handler blocked on `_approval_queue.get`, the main loop couldn't
  read the next stdin command (which is exactly where the
  `extension_ui_response` would arrive). Fixed by dispatching each prompt
  to a daemon thread; stdout writes are serialised through a lock.
- **`no_pi_on_path` fixture**: System-wide `/usr/bin/pi` exists on this
  host. Prepending an empty directory to PATH wasn't enough — the fixture
  now clobbers PATH entirely to guarantee a clean "binary not found"
  state.

## Invariant Coverage Map

| Invariant | Test File | Test |
|-----------|-----------|------|
| #1 — No built-in line iterator in pi_jsonl_reader | `test_pi_jsonl_reader.py` | `test_no_builtin_line_iterators_present` |
| #2 — Unicode separators don't split records | `test_pi_jsonl_reader.py` | `test_unicode_separators_in_json_string_do_not_split` |
| #3 — PiRuntime is constructible (ABC fully implemented) | `test_pi_runtime_abc_compliance.py` | `test_pi_runtime_is_constructible` |
| #4 — MAX_PI_TABS honoured by LRU eviction | `test_pi_runtime_lru_eviction.py` | `test_seventh_tab_evicts_lru` |
| #5 — Idle reaper kills only idle subprocesses | `test_pi_runtime_idle_reaper.py` | `test_reaper_kills_client_idle_past_threshold` + `test_reaper_does_not_kill_recently_active_client` |
| #6 — `extension_ui_request` → `permission.asked` | `test_pi_event_normalization.py` | `test_extension_ui_request_with_iw_approvals_namespace_becomes_permission_asked` |
| #7 — runtime `"pi"` accepted | `test_tab_service_allowlist.py` | `test_create_tab_accepts_runtime_pi` |
| #8 — `pi_extensions_synced` counter increments | `test_sync_agents_extensions.py` | `test_pi_extensions_synced_counter_increments` |
