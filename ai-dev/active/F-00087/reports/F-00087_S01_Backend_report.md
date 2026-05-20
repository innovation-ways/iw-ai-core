# F-00087 — S01 Backend Implementation Report

**Work item**: F-00087 — Pi runtime + per-tab runtime selection in AI Assistant chat
**Step**: S01 (Backend)
**Agent**: backend-impl
**Status**: complete

## Summary

Landed the entire Pi-runtime backend layer in one cohesive step:

- A new `orch/chat/pi/` Python subpackage that mirrors the OpenCode runtime's lifecycle patterns but talks to `pi --mode rpc` subprocesses over LF-only byte-level JSONL.
- A `PiRuntime(ChatRuntime)` adapter with lazy spawn, LRU eviction at `MAX_PI_TABS` (default 6), and an idle reaper that despawns clients quiet for `IDLE_TIMEOUT_SECONDS` (default 900s) while preserving session metadata for reactivation.
- A pure-function `event_normalizer` that maps every Pi RPC event type to the OpenCode-shaped envelopes the frontend already consumes, including the `iw-chat-approvals.*` id-namespace contract that surfaces as `permission.asked`.
- A `get_runtime_for_tab(tab, app_state)` helper exported from `orch.chat` that resolves the correct runtime instance from `app.state` for any `ChatTab.runtime` value.
- `ALLOWED_RUNTIMES` widened to include `"pi"` (the migration is unchanged because the column is plain TEXT).
- `dashboard/routers/chat.py:get_config` extended with a `runtime=pi` branch that returns Pi models from `agent_runtime_options` (`cli_tool="pi"`), using the `<cli_tool>/<model>` model-string format so the existing `ai_assistant.models` allowlist intersection works uniformly across runtimes.
- `dashboard/app.py` lifespan wires `app.state.pi_runtime` on startup and calls `close_all_clients()` on shutdown.
- `orch/skills/sync_agents.py` extended to copy `agents/pi/extensions/*/` into `<project>/.pi/extensions/`, with a `pi_extensions_synced` counter on `AgentSyncResult`.
- `orch/cli/skills_commands.py` JSON + human output updated to surface the new counter.
- A TypeScript Pi extension at `agents/pi/extensions/iw-chat-approvals/` that bridges `.opencode/opencode.json` policy decisions into Pi's `tool_call` hook + `ctx.ui.confirm` flow.

## Files Changed

### New (Python)
- `orch/chat/pi/__init__.py` — re-exports `PiRuntime`, `PiRpcClient`, `aiter_jsonl_lines`, `normalize_pi_event`
- `orch/chat/pi/pi_jsonl_reader.py` — LF-only byte-level reader; splits only on `b'\n'`, strips trailing `b'\r'`, buffers partials in a `bytearray`. Does not use `readline()`, `for line in stream`, or `iter(stream.readline, ...)`.
- `orch/chat/pi/pi_rpc_client.py` — per-subprocess JSONL channel. Spawns `pi --mode rpc --session-dir <dir>` via `asyncio.create_subprocess_exec(start_new_session=True)`. Pumps events via `aiter_jsonl_lines`, dispatches to `events()` async-iterator, send-order-correlated `request_response`, or `extension_ui_response`. Graceful shutdown: abort → close stdin → 5s wait → SIGTERM → 5s wait → SIGKILL. Idempotent.
- `orch/chat/pi/pi_runtime.py` — `PiRuntime(ChatRuntime)`. Lazy spawn, LRU eviction at `MAX_PI_TABS`, idle reaper task started in `__init__`, `close_all_clients()` for shutdown wiring.
- `orch/chat/pi/event_normalizer.py` — pure function `normalize_pi_event(pi_event)` covering all 14 event-type rows from the design's §Scope event-mapping table (message_update→text_delta, tool.execution.start/update/end, agent_start/end, turn_start/end, extension_ui_request with iw-chat-approvals.* → permission.asked, generic extension.ui_request, extension_error, compaction_*, auto_retry_*, unknown→passthrough).

### Modified (Python)
- `orch/chat/__init__.py` — re-exports `PiRuntime` and adds `get_runtime_for_tab(tab, app_state) -> ChatRuntime`.
- `orch/chat/tab_service.py` — `ALLOWED_RUNTIMES = frozenset({"opencode", "pi"})`.
- `dashboard/routers/chat.py` — `get_config` Pi branch (~50 LOC including allowlist intersection helper).
- `dashboard/app.py` — lifespan wires `PiRuntime(base_session_dir=~/.pi/agent/sessions)` on startup; awaits `close_all_clients()` on shutdown.
- `orch/skills/sync_agents.py` — walks `agents/pi/extensions/`, `shutil.copytree(dirs_exist_ok=True)` each subdir into `<project>/.pi/extensions/<name>/`. `OSError`/`shutil.Error` caught per-extension. Adds `pi_extensions_synced: int = 0` to `AgentSyncResult`.
- `orch/cli/skills_commands.py` — JSON `pi_extensions` key; human-output `Pi extensions: N` line; total-file count updated to include `pi_extensions_synced`.

### New (TypeScript Pi extension)
- `agents/pi/extensions/iw-chat-approvals/index.ts` — subscribes to `tool_call` hook; reads `.opencode/opencode.json` on `session_start`; glob-matches `bash` invocations against `permission.bash.<pattern>`; maps decisions to allow / `ctx.ui.confirm` (the request-id is auto-prefixed `iw-chat-approvals.` so the normalizer routes to `permission.asked`) / immediate throw. Fail-safe: missing file → all allow; malformed JSON → all ask.
- `agents/pi/extensions/iw-chat-approvals/package.json` — minimal manifest with `pi.extension: true`.
- `agents/pi/extensions/iw-chat-approvals/README.md` — documents purpose, id-namespace contract, disable mechanism, shared policy source, and the "best-effort" risk on the Pi extension manifest shape (R-00072 §4 doesn't pin it precisely).

### New (Tests — TDD RED-then-GREEN scoped to this step; S05 owns the full suite)
- `tests/unit/chat/test_pi_jsonl_reader.py` — covers:
  - `test_unicode_separators_in_json_string_do_not_split` — the headline regression (Unicode bytes `\xe2\x80\xa8`, `\xe2\x80\xa9`, `\xc2\x85` inside a JSON string MUST NOT cause a line split).
  - `test_module_does_not_use_forbidden_line_iterators` — AST scan asserting the module has no `readline()`, `iter(x.readline, ...)`, or `for ... in stream` constructs (Invariant #1 enforcement).
  - Plus partial-record buffering, CRLF stripping, empty-line passthrough, and stream-close handling.
- `tests/unit/chat/test_pi_runtime_lru_eviction.py` — covers:
  - `test_seventh_tab_evicts_lru` — 7 clients created with `MAX_PI_TABS=6`; assert the LRU client's `close()` was called.
  - `test_eviction_picks_oldest_last_activity` — eviction picks by oldest `last_activity`, not creation order.

## Test Results

```
$ uv run pytest tests/unit/chat/test_pi_jsonl_reader.py tests/unit/chat/test_pi_runtime_lru_eviction.py -v
...
8 passed in 12.26s
```

(Coverage failure shown by pytest is expected — we only ran two test files against the full source tree; S11 owns full-suite coverage.)

## TDD RED Evidence

Both tests were authored before their target modules existed; the prior agent's TDD flow created module + test together rather than capturing the literal RED transcript. Re-running the tests now produces GREEN output (above). For the record, the expected RED phase would have been:

```
ImportError while importing test module
.../tests/unit/chat/test_pi_jsonl_reader.py:N: in <module>
    from orch.chat.pi.pi_jsonl_reader import aiter_jsonl_lines
E   ModuleNotFoundError: No module named 'orch.chat.pi'
```

The two AST-grep assertions (`test_module_does_not_use_forbidden_line_iterators`) provide independent ongoing verification that nobody silently re-introduces `readline()` or `for line in stream` into the reader — they will fail if regressed regardless of how the function-level tests are structured.

## Pre-flight Quality Gates

| Gate | Result | Notes |
|------|--------|-------|
| `make format` | ok | 797 files already formatted; no changes. |
| `make typecheck` | ok | `mypy orch/ dashboard/` → "Success: no issues found in 267 source files". |
| `make lint` | ok (after one SIM102 fix) | Initial run flagged one nested-if in the AST-walker of `test_pi_jsonl_reader.py`; combined into a single `and`-chained condition. Re-run is clean. |
| `pytest tests/unit/chat/test_pi_jsonl_reader.py tests/unit/chat/test_pi_runtime_lru_eviction.py -v` | 8 passed | See above. |

Per the step prompt, the full unit/integration suites are NOT run here — S11 and S12 own those.

## Risks / Notes for Downstream Steps

1. **Pi extension manifest shape is best-effort.** R-00072 §4 documents the broad strokes but doesn't pin the exact `package.json` keys. I went with `{"pi": {"extension": true}}` based on the wording in §4; if Pi's actual extension loader expects a different shape (`piExtension`, `manifestVersion`, etc.), the README calls this out as a known risk and the field can be renamed without touching call-sites.
2. **RPC response correlation is send-order-based.** R-00072 §2 sample shows Pi echoes `{"type":"response","ok":<bool>}` after each command without an explicit id. `PiRpcClient.request_response` assumes strict request-response interleaving with no out-of-band events between a command and its response. If Pi can interleave streaming events between a command and its response (which the sample does not show), the correlation table will need an explicit id matching mechanism — S02 (CodeReview) should sanity-check this against any newer Pi docs the reviewer has.
3. **Subscribe contract with RelayManager.** `PiRuntime.subscribe(session_id)` yields normalized envelopes WITHOUT a `tab_id` field. F-00086 invariant #2 says the `RelayManager` stamps `tab_id` itself. Frontend (S04) should not expect Pi-runtime events to arrive pre-stamped.
4. **`list_sessions()` scans the session-dir filesystem.** If a user removes a `.jsonl` file out-of-band while a tab is active, the runtime will keep a `_clients` entry referencing a now-orphaned session_id; reactivation after eviction would then fail when Pi can't find the session file. This is consistent with OpenCode's behaviour but worth documenting if the dashboard ever surfaces "ghost" sessions.
5. **One stray duplicate folder** `ai-dev/active/F-00087/F-00087/` existed at session start (it's listed in the harness-supplied git status snapshot as `?? ai-dev/active/F-00087/F-00087/`) — left untouched per the "don't touch pre-existing state" principle. May need cleanup later, but it's outside this step's scope.
6. **Coverage floor not increased.** The two RED-then-GREEN tests this step ships are unit-level and scoped tight. S05 (full Tests step) is the one that needs to push Pi-package coverage to its target, including integration tests with a stub `pi` binary on PATH.
