# F-00087_S01_Backend_prompt

**Work Item**: F-00087 -- Pi runtime + per-tab runtime selection in AI Assistant chat
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch DB. This Feature ships NO migration; you do not write or modify migration files.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00087 --json`.
- `ai-dev/active/F-00087/F-00087_Feature_Design.md` — design document (read §Scope, §Acceptance Criteria, §Boundary Behavior, §Invariants in full)
- F-00086 surface this Feature extends:
  - `orch/chat/runtime_base.py` — `ChatRuntime` ABC
  - `orch/chat/tab_service.py` — `ALLOWED_RUNTIMES` constant
  - `orch/chat/opencode/runtime.py` — reference `ChatRuntime` implementation; mirror the same lifecycle patterns
  - `orch/chat/opencode/relay_manager.py` — event shape your normalizer must produce
  - `dashboard/routers/chat.py` — `get_config` handler you extend
  - `dashboard/app.py` — lifespan you extend
- CR-00062 surface this Feature builds on:
  - `agents/pi/` — 30 existing agent files (S04 of CR-00062); your extension lives alongside as `agents/pi/extensions/iw-chat-approvals/`
  - `agent_runtime_options` Pi rows: `(pi, minimax/MiniMax-M2.7)` and `(pi, openai/gpt-5.3-codex)` — seeded by CR-00062
  - `orch/skills/sync_agents.py` — `sync_agents_and_commands()` and `AgentSyncResult` already extended for `pi_agents_synced`; you extend for `pi_extensions_synced`
  - `orch/cli/skills_commands.py` — JSON/human output you extend
- Research: `docs/research/R-00072-pi-dashboard-embedding.md` §2 (RPC mode), §4 (extensions), §7 (permissions), §9 (architecture), §11 (risks). **§2 is mandatory reading before writing pi_jsonl_reader.py.**
- OpenCode policy reference: `.opencode/opencode.json` — the shape the Pi extension reads

## Output Files

Python:
- `orch/chat/pi/__init__.py` — re-exports
- `orch/chat/pi/pi_jsonl_reader.py` — LF-only byte-level reader
- `orch/chat/pi/pi_rpc_client.py` — per-subprocess JSONL channel
- `orch/chat/pi/pi_runtime.py` — `PiRuntime(ChatRuntime)` + process pool
- `orch/chat/pi/event_normalizer.py` — Pi → OpenCode-shaped event translation
- `orch/chat/__init__.py` — add `get_runtime_for_tab(tab)` helper + re-export `PiRuntime`
- `orch/chat/tab_service.py` — extend `ALLOWED_RUNTIMES` by one entry
- `dashboard/routers/chat.py` — `get_config` Pi branch (~30 LOC)
- `dashboard/app.py` — lifespan wiring for `PiRuntime`
- `orch/skills/sync_agents.py` — extension copy + counter
- `orch/cli/skills_commands.py` — JSON + human output additions

TypeScript (the Pi extension):
- `agents/pi/extensions/iw-chat-approvals/index.ts`
- `agents/pi/extensions/iw-chat-approvals/package.json`
- `agents/pi/extensions/iw-chat-approvals/README.md`

Plus targeted RED tests (S05 owns the full suite):
- `tests/unit/chat/test_pi_jsonl_reader.py` — at least the Unicode-separator regression
- `tests/unit/chat/test_pi_runtime_lru_eviction.py` — at least the 7th-tab eviction case

Report:
- `ai-dev/active/F-00087/reports/F-00087_S01_Backend_report.md`

## Context

You are landing the entire Pi-runtime backend in one cohesive step: Python subpackage + TypeScript extension + sync-engine + API + lifespan wiring + allowlist extension. The pieces are tightly coupled — the extension's `ctx.ui.confirm` payload shape MUST match what the Python `event_normalizer` expects — so splitting them across agents would only create cross-step dependencies for ~100 LOC of TypeScript.

Read the design document first; pay particular attention to §Scope's event-mapping table (drives the normalizer), §Boundary Behavior (drives every error path), and §Invariants (your acceptance contract).

## Requirements

### 1. `orch/chat/pi/pi_jsonl_reader.py` — LF-only byte-level reader

**This is the single highest-risk piece.** R-00072 §2 documents the trap: Python's `io.IOBase.readline`, `for line in stream`, and `iter(stream.readline, b"")` all split on Unicode separators (` `, ` `, ``) when those bytes appear inside a JSON string. Pi tool output WILL contain such characters in practice; the protocol breaks silently.

API:

```python
async def aiter_jsonl_lines(stream: asyncio.StreamReader) -> AsyncIterator[bytes]:
    """Yield one complete JSONL record per iteration.

    Splits ONLY on b'\\n' (0x0A). Strips trailing b'\\r' if present.
    Buffers partial records across read calls. Yields each record as raw
    bytes (caller json.loads()s).

    NEVER uses readline(), 'for line in stream', or any Python helper that
    splits on Unicode separators inside strings.
    """
```

Implementation outline: maintain a `bytearray` buffer; `await stream.read(N)` (N=4096 or 8192); scan for `b'\\n'` in the buffer; emit each complete chunk (stripping trailing `b'\\r'`), retain the trailing partial. On `IncompleteReadError` / stream close, yield any remaining buffer if non-empty.

**The first test you write** (TDD RED): `tests/unit/chat/test_pi_jsonl_reader.py::test_unicode_separators_in_json_string_do_not_split`. Feed the reader bytes for `{"text":"line1\\u2028line2"}\\n{"x":1}\\n` (Unicode bytes literal, not escape sequence) and assert exactly TWO records yielded. RED phase: function doesn't exist → `ImportError`. GREEN phase: function exists and passes. Capture the RED output for the report.

Also: a separate test asserts no built-in line iterator is referenced in the module (grep test). Invariant #1.

### 2. `orch/chat/pi/pi_rpc_client.py` — per-subprocess JSONL channel

```python
class PiRpcClient:
    def __init__(self, *, session_dir: Path, env: dict[str, str] | None = None,
                 binary: str = "pi"): ...

    async def start(self) -> None:
        """Spawn `pi --mode rpc --session-dir <dir>` subprocess.
        Uses asyncio.create_subprocess_exec with start_new_session=True
        so SIGTERM to the process group cleans up children.
        """

    async def send_command(self, cmd: dict) -> None:
        """JSON-encode + write '\\n'-terminated to subprocess.stdin."""

    async def events(self) -> AsyncIterator[dict]:
        """Read JSONL events from subprocess.stdout via aiter_jsonl_lines;
        json.loads each record. Yields parsed dicts."""

    async def request_response(self, cmd: dict, *, timeout: float = 30.0) -> dict:
        """Send a command and wait for the matching response by id.
        The Pi RPC protocol echoes a {'type':'response', 'ok':bool} after each
        command (see R-00072 §2 sample). Use that for sync commands like
        get_state, get_messages.
        """

    async def reply_extension_ui(self, request_id: str, value: Any) -> None:
        """Write {'type':'extension_ui_response', 'id':request_id, 'value':value}
        to stdin. Used by the router to relay frontend approval clicks."""

    async def close(self) -> None:
        """Graceful shutdown: send 'abort' command; close stdin; wait 5s for
        subprocess exit; SIGTERM; wait 5s; SIGKILL. Idempotent."""

    @property
    def last_activity(self) -> float: ...  # monotonic timestamp
```

Internally:
- Start a background task `_pump_events()` that calls `aiter_jsonl_lines(self._proc.stdout)`, json.loads each record, and dispatches to either (a) the `events()` AsyncIterator's queue, (b) the `request_response` correlation table (keyed by some id strategy — Pi's RPC echoes type='response' after each command in order; correlate by send-order if no id is in the response), or (c) the extension_ui correlation table (for `extension_ui_request`/`response`).
- Update `last_activity` on every send AND every received event.

### 3. `orch/chat/pi/event_normalizer.py` — Pi → OpenCode-shaped envelopes

Single pure function:

```python
def normalize_pi_event(pi_event: dict) -> dict | None:
    """Translate a Pi RPC event into the OpenCode-shaped envelope the
    frontend chat.js already handles.

    Returns None for events that should be dropped (e.g., session header
    duplicates).

    Mapping table — implement EVERY row from the design §Scope event-mapping table.
    """
```

Required mappings (from design §Scope; every row gets a unit test):

| Pi `type` | OpenCode envelope |
|-----------|-------------------|
| `message_update` (sub-event `text_delta`) | `{"event":"message.part.added","data":{"part":{"type":"text","text":<delta>}}}` |
| `tool_execution_start` | `{"event":"tool.execution.start","data":{...}}` (preserve tool name, args) |
| `tool_execution_update` | `{"event":"tool.execution.update","data":{...}}` |
| `tool_execution_end` | `{"event":"tool.execution.end","data":{...}}` (preserve result) |
| `agent_start` | `{"event":"session.start","data":{...}}` |
| `agent_end` | `{"event":"session.idle","data":{...}}` |
| `turn_start` / `turn_end` | passthrough as `{"event":"<type>",...}` |
| `extension_ui_request` with id starting `"iw-chat-approvals."` | `{"event":"permission.asked","data":{"id":<id>,"tool":<tool>,"args":<args>,"question":<q>}}` (extension enriches the original payload — see §6 below) |
| `extension_ui_request` with any other id | passthrough as `{"event":"extension.ui_request","data":<original>}` |
| `extension_error` | `{"event":"session.error","data":{...}}` |
| `compaction_start`/`compaction_end` | passthrough |
| `auto_retry_start`/`auto_retry_end` | passthrough |
| unknown `type` | passthrough as `{"event":<type>,"data":<original>}` |

Stamping `"tab_id"` is the RelayManager's job (F-00086 invariant #2); the normalizer does NOT add it.

### 4. `orch/chat/pi/pi_runtime.py` — `PiRuntime(ChatRuntime)`

```python
MAX_PI_TABS = int(os.environ.get("IW_CORE_MAX_PI_TABS", "6"))
IDLE_TIMEOUT_SECONDS = int(os.environ.get("IW_CORE_PI_IDLE_TIMEOUT", "900"))

class PiRuntime(ChatRuntime):
    def __init__(self, *, base_session_dir: Path | None = None,
                 env: dict[str, str] | None = None,
                 binary: str = "pi"): ...
```

State:
- `self._clients: dict[str, PiRpcClient]` — keyed by session_id (uuid string)
- `self._client_tab_meta: dict[str, dict]` — per-client `{last_activity, pi_session_path}`
- `self._reaper_task: asyncio.Task` — started in `__init__`, ticks every 60s

Behaviour:

- `health()` — returns True iff `shutil.which(self._binary)` is truthy. Cheap; no subprocess spawn.
- `create_session(model=None, agent=None, directory=None) -> str` — generates a fresh UUID, reserves a slot in `_clients` map (value=None initially); LAZY spawn (first `prompt`/`subscribe` triggers `_get_or_spawn_client(session_id)`). When `len(active_clients) >= MAX_PI_TABS`, evict the LRU client (terminate via `close()`); the evicted session's metadata persists, so reactivation respawns with `pi --session <persisted_path>`. The persisted `pi_session_path` is the JSONL session file Pi writes under `--session-dir`.
- `prompt(session_id, text, model=None, system=None)` — `_get_or_spawn_client(session_id).send_command({"type":"prompt","message":text,...})`. If `model` differs from current, prepend a `set_model` command.
- `abort(session_id)` — `send_command({"type":"abort"})` to the client.
- `reply_permission(session_id, request_id, response, remember=False)` — translates `response` ("approve"/"deny") to bool and calls `client.reply_extension_ui(request_id, bool_value)`.
- `set_model(session_id, model)` — `send_command({"type":"set_model","model":model})`.
- `subscribe(session_id, last_event_id=None)` — `async for ev in client.events(): yield normalize_pi_event(ev)` (None values filtered out).
- `get_messages(session_id)` — `client.request_response({"type":"get_messages"})`.
- `get_session(session_id)` — `{"id": session_id, "pi_session_path": <path>}`.
- `list_sessions()` — scan `base_session_dir/` for `.jsonl` files and return their session header info. Used by F-00086's `bootstrap_default_tab` (no-op for Pi tabs in F-B; F-00086's bootstrap only ever seeds OpenCode tabs).
- `close_session(session_id)` — `await client.close()`; remove from `_clients`.
- `get_config()` / `get_providers()` — return empty/stub structures; F-B reads Pi models from `agent_runtime_options` in the router, not from the runtime instance. Document this in the docstring.

Idle reaper:

```python
async def _reaper_loop(self):
    while True:
        await asyncio.sleep(60)
        now = time.monotonic()
        to_evict = [sid for sid, meta in self._client_tab_meta.items()
                    if (now - meta["last_activity"]) > IDLE_TIMEOUT_SECONDS]
        for sid in to_evict:
            if sid in self._clients and self._clients[sid] is not None:
                await self._clients[sid].close()
                self._clients[sid] = None  # mark as despawned but reserved
```

LRU eviction at MAX_PI_TABS: when `_get_or_spawn_client` would push active count > cap, pick the entry with the oldest `last_activity` and `close()` it before spawning the new one. The freshly-spawned client's `last_activity` is set to now.

**TDD RED test** (write before implementation): `tests/unit/chat/test_pi_runtime_lru_eviction.py::test_seventh_tab_evicts_lru`. Mock `PiRpcClient` (don't spawn real subprocesses); create 7 clients; assert the LRU client's `close()` was called. RED phase: module doesn't exist → ImportError.

### 5. `orch/chat/__init__.py` — `get_runtime_for_tab` helper + re-exports

```python
def get_runtime_for_tab(tab: ChatTab, app_state) -> ChatRuntime:
    """Resolve the per-runtime instance from app state by tab.runtime.

    Raises ValueError on unknown runtime (defensive — tab_service.ALLOWED_RUNTIMES
    is the source of truth, but this catches drift).
    """
    if tab.runtime == "opencode":
        return app_state.opencode_runtime
    if tab.runtime == "pi":
        return app_state.pi_runtime
    raise ValueError(f"unknown runtime {tab.runtime!r}")
```

Re-export `PiRuntime` from `orch.chat`.

### 6. `agents/pi/extensions/iw-chat-approvals/index.ts` — the TypeScript Pi extension

Subscribes to Pi's `tool_call` hook. The hook callback receives `{tool, args, ctx}`. The extension:

1. On `session_start`: read `<repo_root>/.opencode/opencode.json` and parse `permission` key. Cache on the extension instance. Fail-safe: missing file → all "allow"; malformed JSON → all "ask" (so users see prompts rather than silent execution of unrecognised commands).
2. On `tool_call`: match the tool+args against the policy.
   - For `bash` tool: glob-match against `permission.bash.<pattern>`; first-match wins; default if no match is `"allow"` (mirroring opencode.json's `"*": "allow"` precedent).
   - For other tools: match against `permission.external_directory` if applicable; else default `"allow"`.
3. If decision is `"allow"`: return immediately (no-op).
4. If decision is `"ask"`: call `await ctx.ui.confirm({tool, args, question: <human-readable description>})`. The id of the confirm request is auto-prefixed with `"iw-chat-approvals."` so the event normalizer can route it. On approval, return; on denial, throw `new Error("Tool call denied by user")` (this aborts the tool execution per R-00072 §4).
5. If decision is `"deny"`: throw immediately.

Minimal `package.json`:
```json
{
  "name": "iw-chat-approvals",
  "version": "0.1.0",
  "description": "IW AI Core chat approval policy bridge (Pi extension)",
  "main": "index.ts",
  "pi": { "extension": true }
}
```

(Verify the exact extension manifest shape against R-00072 §4 docs or the existing CR-00062 `agents/pi/*.md` files; if R-00072 doesn't pin it precisely, model on the most-recent Pi extension reference you can find — that's a documented "best-effort" risk in the design.)

`README.md`: one page documenting:
- What the extension does
- The `iw-chat-approvals.*` id namespace contract
- How to disable it (remove from `.pi/extensions/`)
- How the policy file is shared with OpenCode

### 7. `dashboard/routers/chat.py:get_config` — Pi branch

Today (after F-00086) the handler returns OpenCode providers. Add a branch:

```python
runtime = request.query_params.get("runtime", "opencode")
if runtime == "pi":
    rows = db.execute(
        select(AgentRuntimeOption)
        .where(AgentRuntimeOption.cli_tool == "pi", AgentRuntimeOption.enabled.is_(True))
        .order_by(AgentRuntimeOption.sort_order)
    ).scalars().all()
    available_models = [f"{r.cli_tool}/{r.model}" for r in rows]
    default_model = next((m for r, m in ((r, f"{r.cli_tool}/{r.model}") for r in rows) if r.is_default), available_models[0] if available_models else "")
    # apply ai_assistant.models allowlist intersection same as opencode branch
    ...
elif runtime == "opencode":
    # existing logic
```

Keep the `ai_assistant.models` allowlist intersection identical to the OpenCode branch; the model-string format is `<cli_tool>/<model>` so allowlists work uniformly.

### 8. `dashboard/app.py` — lifespan wires PiRuntime

Add after the existing OpenCode lifespan setup:

```python
pi_runtime = PiRuntime(base_session_dir=Path.home() / ".pi" / "agent" / "sessions")
app.state.pi_runtime = pi_runtime
```

On shutdown: `await pi_runtime.close_all_clients()` (add a helper method to PiRuntime that iterates `_clients.values()` and closes each).

### 9. `orch/skills/sync_agents.py` — copy `agents/pi/extensions/`

Add to `AgentSyncResult`:
```python
pi_extensions_synced: int = 0
```

In `sync_agents_and_commands()`, after the existing agent-copy loop, walk `<platform_root>/agents/pi/extensions/`. For each subdir, `shutil.copytree(src, dst, dirs_exist_ok=True, copy_function=shutil.copy2)` into `<project_repo_root>/.pi/extensions/<name>/`. Increment `pi_extensions_synced` per successful copy.

Catch `OSError`/`shutil.Error` from broken symlinks, log a warning, continue with other extensions.

### 10. `orch/cli/skills_commands.py` — output additions

JSON output: add `"pi_extensions": result.pi_extensions_synced` key.
Human output: add `Pi extensions: {n}` line, parallel to existing `Pi agents: {n}` line. Update the total file count to include `pi_extensions_synced`.

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, `tests/CLAUDE.md`, `dashboard/CLAUDE.md`. Critical:
- SQLAlchemy 2.0 sync style.
- `asyncio.create_subprocess_exec` not `subprocess.Popen` (we're in async land).
- Match the OpenCode runtime's lifecycle patterns in `orch/chat/opencode/runtime.py` for subprocess management, watchdogs, and graceful shutdown.
- Testcontainer fixture rules (apply `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck` — must report zero errors involving the files you touched
3. `make lint`
4. `uv run pytest tests/unit/chat/test_pi_jsonl_reader.py tests/unit/chat/test_pi_runtime_lru_eviction.py -v` — your two TDD-RED tests must now be GREEN

Do NOT run the full unit/integration suite — S11/S12 own those.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00087",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/chat/__init__.py",
    "orch/chat/pi/__init__.py",
    "orch/chat/pi/pi_jsonl_reader.py",
    "orch/chat/pi/pi_rpc_client.py",
    "orch/chat/pi/pi_runtime.py",
    "orch/chat/pi/event_normalizer.py",
    "orch/chat/tab_service.py",
    "dashboard/routers/chat.py",
    "dashboard/app.py",
    "orch/skills/sync_agents.py",
    "orch/cli/skills_commands.py",
    "agents/pi/extensions/iw-chat-approvals/index.ts",
    "agents/pi/extensions/iw-chat-approvals/package.json",
    "agents/pi/extensions/iw-chat-approvals/README.md",
    "tests/unit/chat/test_pi_jsonl_reader.py",
    "tests/unit/chat/test_pi_runtime_lru_eviction.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "tests/unit/chat/test_pi_jsonl_reader.py: X passed; tests/unit/chat/test_pi_runtime_lru_eviction.py: Y passed",
  "tdd_red_evidence": "tests/unit/chat/test_pi_jsonl_reader.py::test_unicode_separators_in_json_string_do_not_split — ImportError: cannot import name 'aiter_jsonl_lines' (RED captured before module creation)",
  "blockers": [],
  "notes": ""
}
```
