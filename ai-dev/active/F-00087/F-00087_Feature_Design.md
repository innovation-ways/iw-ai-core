# F-00087: Pi runtime + per-tab runtime selection in AI Assistant chat

**Type**: Feature
**Priority**: Medium
**Created**: 2026-05-19
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. This Feature adds an `orch/chat/pi/` Python subpackage, a TypeScript Pi extension under `agents/pi/extensions/iw-chat-approvals/`, sync-engine + API + frontend wiring, and tests with a stub `pi` binary on PATH. No new Docker usage. Testcontainer fixtures remain the only allowed exception.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This Feature adds NO Alembic migration.** The `chat_tabs.runtime` column (created by F-00086) already accepts arbitrary text — allowlist is enforced in `orch/chat/tab_service.py:ALLOWED_RUNTIMES`, extending that constant from `{"opencode"}` to `{"opencode", "pi"}` is the only code change to the runtime-allowlist surface. The Pi catalogue rows in `agent_runtime_options` were seeded by CR-00062 (already merged); no schema changes required.

## Description

Add Pi (pi.dev) as a second selectable chat runtime alongside OpenCode in the multi-tab AI Assistant. Each Pi tab gets its own `pi --mode rpc` subprocess managed by a process pool with LRU eviction (cap `MAX_PI_TABS=6`) and a 15-minute idle reaper. A TypeScript Pi extension subscribes to Pi's `tool_call` hook, reads the existing `.opencode/opencode.json` permission policy (one policy file per project, shared across runtimes), and surfaces approval requests via the same frontend modal F-00086 uses for OpenCode — so the user experience for risky tool calls is identical regardless of which runtime a tab is using.

## Project Context

Read the project's `CLAUDE.md` for orchestration architecture, the hard rules (testcontainers only for live DB, no `importlib.reload(orch.config)`, no `docker compose up` against the orch DB, FTS DDL hook, `DaemonEvent.event_metadata`, Jinja2 `%`-style `|format` filter calls), and the dashboard build conventions. Read `dashboard/CLAUDE.md` for routing/template/htmx patterns and the clipboard helper rule. Read `tests/CLAUDE.md` for fixture rules. Read `docs/research/R-00072-pi-dashboard-embedding.md` — especially §2 (RPC mode protocol), §4 (extension system), §7 (permissions & sandbox), §9 (architecture sketch), §11 (risks). Read CR-00062's design (`ai-dev/active/CR-00062/`) for the `agents/pi/` master tree shape and the `agent_runtime_options` Pi rows. F-00086's design (`ai-dev/active/F-00086/`) is the foundation this Feature builds on — read its §Scope and §Invariants in full.

## Scope

### In Scope

- **New `orch/chat/pi/` subpackage**:
  - `orch/chat/pi/__init__.py` — re-exports `PiRuntime`, `PiRpcClient`, `MAX_PI_TABS`, `IDLE_TIMEOUT_SECONDS`.
  - `orch/chat/pi/pi_jsonl_reader.py` — **raw-bytes reader that splits ONLY on `b"\n"`** (per R-00072 §2 — Python's `io.IOBase.readline` and `for line in stream` split on Unicode separators inside JSON strings and will silently corrupt Pi's protocol). API: `async def aiter_jsonl_lines(stream: asyncio.StreamReader) -> AsyncIterator[bytes]` yields one complete JSONL record per iteration after stripping trailing `\r`.
  - `orch/chat/pi/pi_rpc_client.py` — `PiRpcClient`: opens `asyncio.create_subprocess_exec("pi", "--mode", "rpc", "--session-dir", session_dir, ...)`, exposes `async send_command(cmd: dict) -> None` (JSON-encodes + writes `\n`-terminated to stdin), `async events() -> AsyncIterator[dict]` (yields normalized events from stdout), `async request_response(command, *, timeout=30) -> dict` for synchronous commands (e.g., `get_messages`), `async close() -> None` (graceful shutdown via SIGTERM → SIGKILL fallback). Correlates `extension_ui_response` to `extension_ui_request` by `id` field.
  - `orch/chat/pi/pi_runtime.py` — `class PiRuntime(ChatRuntime)`: maintains `dict[tab_id, PiRpcClient]` of active subprocesses; `create_session()` returns a UUID stored in the client map but the actual subprocess spawn is **lazy** (first `prompt()` or `subscribe()` call); `close_session()` terminates the subprocess; idle reaper task started in `__init__` runs every 60s and culls clients with `last_activity > 15min`; LRU eviction at `MAX_PI_TABS=6` (default; module constant) evicts the least-recently-used client when create_session would push the active count over the cap.
  - `orch/chat/pi/event_normalizer.py` — translates Pi's JSONL events to the OpenCode-shaped envelopes the frontend already consumes:

    | Pi event | Normalized event | Notes |
    |----------|------------------|-------|
    | `message_update` with `assistantMessageEvent.type=text_delta` | `message.part.added` with `part.type=text` and `part.text=<delta>` | streaming token delivery |
    | `tool_execution_start` | `tool.execution.start` | preserves `tool` name, `args` |
    | `tool_execution_update` | `tool.execution.update` | |
    | `tool_execution_end` | `tool.execution.end` | preserves result |
    | `agent_start` | `session.start` | |
    | `agent_end` | `session.idle` | |
    | `turn_start` / `turn_end` | passthrough as-is | (these are extra in Pi's protocol; frontend ignores unknown event types) |
    | `extension_ui_request` (filtered for our extension's id namespace `iw-chat-approvals.*`) | `permission.asked` with `{id, tool, args, question}` from the extension's enriched payload | bridges to F-00086's approval modal |
    | `extension_ui_request` (any other id namespace) | passthrough as `extension.ui_request` | preserves future extensibility |
    | `extension_error` | `session.error` | |
    | `compaction_start` / `compaction_end` | passthrough | |
    | `auto_retry_start` / `auto_retry_end` | passthrough | |

    Every normalized event has a top-level `"tab_id"` field stamped by `RelayManager` (F-00086 invariant #2).
- **Runtime allowlist extension**: `orch/chat/tab_service.py:ALLOWED_RUNTIMES = frozenset({"opencode", "pi"})` — one-line change. The error message format ("runtime '<x>' not in allowlist {...}") is unchanged.
- **API**: `dashboard/routers/chat.py:get_config` extended: when `runtime=pi`, models come from `SELECT cli_tool, model, display_name, is_default FROM agent_runtime_options WHERE cli_tool='pi' AND enabled=true ORDER BY sort_order` (rows seeded by CR-00062: `(pi, minimax/MiniMax-M2.7)` and `(pi, openai/gpt-5.3-codex)`). Response shape unchanged. The `ai_assistant.models` per-project allowlist filter in F-00086's existing logic still applies — Pi models intersected with the project's allowlist, falling back to all Pi models if intersection is empty. **No new endpoints.**
- **Runtime dispatch in `dashboard/app.py`**: lifespan instantiates both `OpencodeRuntime` and `PiRuntime` and stores them on `request.app.state` under keyed names (`opencode_runtime`, `pi_runtime`); router resolves `runtime = app.state.<tab.runtime>_runtime` before each per-tab operation. Add a small `get_runtime_for_tab(tab)` helper in `orch/chat/__init__.py`.
- **TypeScript Pi extension `agents/pi/extensions/iw-chat-approvals/`**:
  - `index.ts` — exports `pi.registerExtension({...})` body. Subscribes to `tool_call` hook. Loads policy from `<project_root>/.opencode/opencode.json` `permission` key (read once at session_start; cached on the extension instance; refetched if file mtime changes — best-effort). For each `tool_call`, matches the policy pattern; if `"ask"`, calls `ctx.ui.confirm({tool, args, question})` and blocks on response; if `"allow"`, returns immediately; if `"deny"`, throws to block execution.
  - `package.json` — minimal Pi extension manifest (name, version, main entry).
  - `README.md` — one-pager describing what the extension does, how it integrates with the IW chat approval modal, and the `iw-chat-approvals.*` id namespace contract.
- **Sync-engine extension** (`orch/skills/sync_agents.py`):
  - Add `pi_extensions_synced: int = 0` field to the `AgentSyncResult` dataclass.
  - In `sync_agents_and_commands()`, after copying agents, walk `agents/pi/extensions/` and copy each subdir (preserving structure including `package.json`, `index.ts`, `README.md`, any `node_modules/` if present) into `<project>/.pi/extensions/<name>/`. Use `shutil.copytree(src, dst, dirs_exist_ok=True, copy_function=shutil.copy2)` to preserve mtimes; symlinks within `node_modules/` are followed by default (acceptable for v1; document the trade-off).
  - Increment `pi_extensions_synced` for each top-level extension dir copied.
- **CLI extension** (`orch/cli/skills_commands.py`):
  - Add `pi_extensions` key to the JSON output of `iw sync-agents --json`.
  - Add a "Pi extensions: <n>" line to the human-readable output.
  - Update the total file count to include `pi_extensions_synced`.
- **Frontend** (`dashboard/templates/chat_assistant/create_tab_modal.html`, `dashboard/static/chat_assistant/chat.js`):
  - The runtime dropdown in the create-tab modal gains a second option: `"Pi"`. Default remains `"OpenCode"`.
  - Selecting a runtime in the modal triggers a model-dropdown re-fetch: `GET /api/chat/config?project_id=X&runtime=<selected>` populates the model list.
  - The per-tab model dropdown (above the composer) ALSO re-fetches when the active tab is a Pi tab — and **only allows Pi models** for that tab (no cross-runtime model switching; changing runtime would mean closing the tab and creating a new one).
- **Tests** (full inventory in §TDD Approach):
  - Unit: 4 new files under `tests/unit/chat/` covering the JSONL reader (Unicode-separator regression), the RPC client (`extension_ui_request`/`response` id correlation), the runtime (LRU eviction, idle reaper, lazy spawn), and the event normalizer (every Pi event type mapped).
  - Integration: 3 new files under `tests/integration/` covering mixed OpenCode+Pi tab independence, the Pi approval flow end-to-end (stub `pi` binary + stub extension), and the sync engine's extension copy.

### Out of Scope

- **Sandboxing**. Pi runs with full user filesystem/network permissions per R-00072 §7 — production sandboxing (containers, namespaces, network egress restriction) is a separate concern tracked outside this Feature.
- **Crash-recovery reaper for orphaned subprocesses.** The 15-minute idle reaper handles the graceful case (long-running tab forgotten). If the dashboard process itself crashes mid-stream, Python's child-process cleanup (via `start_new_session=True` + signal propagation in the subprocess group) handles most cases; a SIGCHLD-watching reaper for edge cases is a follow-up.
- **Auto-migration of existing OpenCode tabs to Pi.** Users explicitly create new Pi tabs via the modal; no batch migration tool.
- **MCP integration on Pi.** Pi explicitly rejects MCP per R-00072 §4; preserving MCP portability is an OpenCode-only property.
- **`/api/chat/skills` differentiation by runtime.** The skills endpoint returns the same Agent-Skills-standard skills list for both runtimes (Pi reads the same `skills/` tree per R-00072 §4). No runtime parameter added.
- **Pi-specific session-tree branching UI.** Pi's JSONL session format supports branching (R-00072 §5); the dashboard treats Pi sessions as linear (matching the OpenCode UX). Branching is a future feature.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | (a) `orch/chat/pi/` Python subpackage (jsonl_reader, rpc_client, runtime, event_normalizer); (b) `orch/chat/pi/__init__.py` re-exports; (c) `tab_service.ALLOWED_RUNTIMES` extension; (d) `dashboard/routers/chat.py:get_config` Pi branch reading from `agent_runtime_options`; (e) `dashboard/app.py` lifespan wiring for `PiRuntime`; (f) `get_runtime_for_tab(tab)` helper in `orch/chat/__init__.py`; (g) `agents/pi/extensions/iw-chat-approvals/` (`index.ts`, `package.json`, `README.md`); (h) `orch/skills/sync_agents.py` extension-copy logic + `pi_extensions_synced` field; (i) `orch/cli/skills_commands.py` JSON + human output additions | — |
| S02 | `code-review-impl` | Per-agent review of S01 (LF-only reader correctness, LRU eviction + idle reaper safety, event normalization completeness, policy parsing correctness, lazy spawn semantics, sync-engine extension copy preserves mtime/structure) | — (after S01) |
| S03 | `code-review-fix-impl` | Apply CRITICAL/HIGH/MEDIUM(fixable) findings from S02 | — (after S02) |
| S04 | `frontend-impl` | Runtime dropdown in `create_tab_modal.html` gains "Pi" option; `chat.js` re-fetches `/api/chat/config?runtime=<selected>` on runtime change; per-tab model dropdown restricts options to the active tab's runtime; minimal CSS for the dropdown change (or none if Tailwind utility classes suffice) | — (after S03) |
| S05 | `tests-impl` | Unit (4 files) + integration (3 files) + stub `pi` binary at `tests/integration/stubs/pi` (3-line bash) + sync engine test for extension copy | — (after S04) |
| S06 | `code-review-final-impl` | Cross-agent global review: ABC contract honoured by `PiRuntime`; event normalizer maps every Pi event type the frontend handles; approval round-trip works end-to-end (Pi extension → `extension_ui_request` → relay → frontend modal → POST permission → stdin `extension_ui_response`); sync engine extension copy doesn't break the existing 30 `agents/pi/*.md` files (CR-00062) | — (after S05) |
| S07 | `code-review-fix-final-impl` | Apply CRITICAL/HIGH/MEDIUM(fixable) findings from S06 | — (after S06) |
| S08 | `qv-gate` (`lint`) | `make lint` | — |
| S09 | `qv-gate` (`format`) | `make format-check` | — |
| S10 | `qv-gate` (`typecheck`) | `make type-check` | — |
| S11 | `qv-gate` (`unit-tests`) | `make test-unit` | — |
| S12 | `qv-gate` (`integration-tests`) | `make test-integration` (timeout 1800) | — |
| S13 | `qv-browser` | Browser verification: capture pre-state of the OpenCode-only dropdown (F-00086 baseline); create 1 OpenCode tab + 2 Pi tabs with different Pi models; send prompts in all three concurrently; abort one Pi tab; trigger a `bash` "ask" pattern on a Pi tab and verify the approval modal; reload page and verify all tabs persist (subprocess respawns lazily on activate) | — |
| S14 | `self-assess-impl` | Self-assessment via `iw-item-analyze` skill (last step — sees full retry/fix-cycle history) | — |

Agent slugs verified against `skills/iw-workflow/SKILL.md`'s canonical agent table and `executor/step_executor_lib.sh`. No Database step (no schema change). The Pi TypeScript extension is owned by `backend-impl` rather than `template-impl` because it is server-side code (runs in the Pi subprocess, Node-side) — not document/template rendering.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No Alembic revision in this Feature.

### API Changes

- **New endpoints**: None
- **Modified endpoints**:
  - `GET /api/chat/config` — when `runtime=pi`, response `models` list comes from `agent_runtime_options WHERE cli_tool='pi' AND enabled=true`, intersected with the project's `ai_assistant.models` allowlist (same logic F-00086 uses for OpenCode). Response shape unchanged.
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None (no new templates)
- **Modified components**:
  - `dashboard/templates/chat_assistant/create_tab_modal.html` — runtime dropdown gains second `<option>` value `"pi"` label `"Pi"`.
  - `dashboard/static/chat_assistant/chat.js` — runtime-change listener re-fetches model list; per-tab model dropdown filtered by runtime.
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/F-00087/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00087_Feature_Design.md` | Design | This document |
| `F-00087_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00087_S01_Backend_prompt.md` | Prompt | S01 — `backend-impl` |
| `prompts/F-00087_S02_CodeReview_prompt.md` | Prompt | S02 — `code-review-impl` |
| `prompts/F-00087_S03_CodeReviewFix_prompt.md` | Prompt | S03 — `code-review-fix-impl` |
| `prompts/F-00087_S04_Frontend_prompt.md` | Prompt | S04 — `frontend-impl` |
| `prompts/F-00087_S05_Tests_prompt.md` | Prompt | S05 — `tests-impl` |
| `prompts/F-00087_S06_CodeReview_Final_prompt.md` | Prompt | S06 — `code-review-final-impl` |
| `prompts/F-00087_S07_CodeReviewFix_Final_prompt.md` | Prompt | S07 — `code-review-fix-final-impl` |
| `prompts/F-00087_S13_BrowserVerification_prompt.md` | Prompt | S13 — `qv-browser` |
| `prompts/F-00087_S14_SelfAssess_prompt.md` | Prompt | S14 — `self-assess-impl` |

(S08–S12 are QV gates — command-only, no prompt files.)

Reports are created during execution in `ai-dev/active/F-00087/reports/`.

## Acceptance Criteria

### AC1: Mixed OpenCode + Pi tabs run independently

```
Given the dashboard is open at /project/iw-ai-core/ with F-00086 deployed
And the AI Assistant panel is expanded
When the user creates Tab O with runtime=opencode model=anthropic/claude-sonnet-4-7
And the user creates Tab P1 with runtime=pi model=minimax/MiniMax-M2.7
And the user creates Tab P2 with runtime=pi model=openai/gpt-5.3-codex
And the user sends a prompt in each tab in succession
Then each tab's stream emits events tagged with its own tab_id
And no event is delivered to a tab whose tab_id does not match
And aborting Tab P1 does not interrupt Tab O or Tab P2
And the Pi subprocess for Tab P1 receives the abort command but the Pi subprocess for Tab P2 continues running
```

### AC2: LF-only JSONL parsing handles Unicode line separators inside JSON strings

```
Given a Pi subprocess emits a JSONL event whose body contains " " or " " or "" inside a string field (for example a tool result containing a Unicode line separator)
When pi_jsonl_reader.aiter_jsonl_lines() consumes the stream
Then exactly one record per LF byte is yielded
And the embedded Unicode separators appear verbatim inside the parsed JSON string
And the JSON loads cleanly via json.loads()
And NO Python built-in line iterator (readline, "for line in stream") is used anywhere in pi_jsonl_reader.py (verified by grep)
```

### AC3: Approval modal works on Pi tabs

```
Given a Pi tab P1 is active
And .opencode/opencode.json contains permission.bash["rm *"] = "ask"
When the user sends a prompt that causes the Pi agent to invoke bash with "rm temp.txt"
Then the iw-chat-approvals extension intercepts the tool_call
And calls ctx.ui.confirm with an enriched payload {tool: "bash", args: {...}, question: "..."}
And the RPC layer emits an extension_ui_request event with id starting "iw-chat-approvals."
And the event_normalizer translates it to a permission.asked event
And the existing F-00086 approval modal renders with the tool name and args
And clicking Approve sends POST /api/chat/tabs/{P1}/permissions/{rid} with response="approve"
And the router writes {"type":"extension_ui_response","id":rid,"value":true} to the Pi subprocess stdin
And the agent proceeds to execute the bash command
```

### AC4: LRU eviction at MAX_PI_TABS=6

```
Given 6 Pi tabs are active, each with a running subprocess
And Tab P1 has been most-recently-used least-recently (oldest last_activity)
When the user creates a 7th Pi tab P7 and sends a prompt in it
Then create_session for P7 succeeds (HTTP 201)
And the chat_tabs row for P7 is persisted
And the Pi subprocess for P1 is terminated (SIGTERM, with SIGKILL fallback after 5 seconds)
And the chat_tabs row for P1 remains intact (status='active', opencode_session_id IS NULL — Pi tabs don't use that column, but pi_session_path is preserved on tab.config or similar)
And subsequently clicking Tab P1 spawns a fresh subprocess via `pi --session <pi_session_path>` resuming the conversation
And the 6-active-subprocess cap continues to hold throughout
```

### AC5: Idle reaper kills subprocess after 15 minutes

```
Given Tab P3 is active with a running Pi subprocess
And the last activity (prompt, abort, permission reply, or message_update event) was 15 minutes ago
When the idle reaper task runs (every 60 seconds)
Then the Pi subprocess for P3 is terminated (SIGTERM with SIGKILL fallback)
And the chat_tabs row for P3 remains intact (status='active')
And no event is emitted to the frontend about the termination
And when the user clicks P3, a fresh subprocess is spawned via `pi --session <path>` and the conversation resumes
And the IDLE_TIMEOUT_SECONDS constant (default 900) is configurable via env var IW_CORE_PI_IDLE_TIMEOUT for ops-tuning
```

### AC6: Event normalization — Pi events arrive in OpenCode shape

```
Given the event_normalizer is given each documented Pi event type in turn
When normalize_event(pi_event) is called
Then for every Pi event type listed in §Scope's event-mapping table the corresponding OpenCode-shaped envelope is produced
And the tab_id field is preserved (added by the RelayManager wrapper, not by the normalizer itself)
And unknown event types pass through with their original "type" field intact (frontend ignores unknown types)
And the frontend chat.js event dispatch handles a synthetic Pi-originated message.part.added event identically to an OpenCode-originated one (verified by integration test)
```

### AC7: Sync engine copies Pi extensions

```
Given agents/pi/extensions/iw-chat-approvals/ exists with index.ts, package.json, README.md
When `uv run iw sync-agents` is run for a registered project
Then the project's .pi/extensions/iw-chat-approvals/ directory exists
And contains index.ts, package.json, README.md byte-identical to the source
And the CLI human output prints "Pi extensions: 1" alongside the existing Claude/OpenCode/Pi-agents lines
And the CLI --json output includes a "pi_extensions" key with value 1
And the AgentSyncResult dataclass has a pi_extensions_synced field defaulting to 0
And re-running sync-agents is idempotent (counter and file content unchanged)
And the existing 30 agents/pi/*.md files (from CR-00062) are still synced correctly — no regression in pi_agents_synced
```

### AC8: Runtime dropdown offers Pi; per-tab model dropdown is runtime-scoped

```
Given the create-tab modal is open
When the user clicks the "Runtime" dropdown
Then two options are listed: "OpenCode" (default) and "Pi"
And selecting "Pi" re-fetches GET /api/chat/config?project_id=iw-ai-core&runtime=pi
And the model dropdown populates with rows from agent_runtime_options WHERE cli_tool='pi' (intersected with project ai_assistant.models if configured)
And selecting "OpenCode" re-fetches with runtime=opencode and restores OpenCode models
And after creating a Pi tab, the per-tab model dropdown above the composer offers ONLY Pi models (no OpenCode models leak in)
And the API endpoint POST /api/chat/tabs accepts {runtime: "pi", model: "<pi-model>"} and rejects {runtime: "pi", model: "<opencode-only-model>"} with HTTP 400
```

## Boundary Behavior

Every row becomes a mandatory test case.

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Pi subprocess fails to spawn (binary missing) | `pi` not on PATH | `PiRuntime.create_session` raises `RuntimeError("pi binary not found on PATH")`; API maps to 503 with `{"error":"Pi runtime unavailable: pi binary not found"}` |
| Pi subprocess dies mid-stream | subprocess exit code != 0 unexpectedly | Emit `session.error` event with the exit code and last 50 lines of stderr; chat_tabs row stays active; user can retry by sending another prompt (lazy respawn) |
| `extension_ui_request` arrives but no matching extension id | id namespace not `iw-chat-approvals.*` | Pass through as `extension.ui_request` event (frontend ignores; future-proofing) |
| `extension_ui_response` written to stdin while subprocess is dead | race between user approval click and reaper | `PiRpcClient.send_command` returns silently (no exception); router logs a warning; frontend modal already cleared on the death event |
| Concurrent prompts in same tab | second `prompt` sent before first finishes | Second command sent with `streamingBehavior: "steer"` per R-00072 §2 (queues mid-turn) |
| Tab P closed via API while subprocess is mid-stream | DELETE /api/chat/tabs/P | `PiRuntime.close_session` sends `abort` then SIGTERM; subprocess removed from pool; pi_session_path preserved on the (now closed) tab row; reopen restores it |
| Policy file `.opencode/opencode.json` missing | file does not exist at session start | Extension defaults to `"allow"` for all tools (preserves today's iw-ai-core "all allow" behaviour); logs once at session start |
| Policy file malformed JSON | `JSONDecodeError` reading the file | Extension defaults to `"ask"` for all tools (fail-safe to user prompts); logs the parse error once |
| Stub `pi` binary in tests prints a string with embedded ` ` | regression case from R-00072 §2 | `aiter_jsonl_lines` yields exactly one record; `json.loads()` succeeds; the Unicode separator survives intact |
| 7th Pi tab created when no clients are idle | all 6 actively streaming | LRU eviction still fires on the least-recently-active client (last_activity timestamp wins regardless of streaming state); the evicted client's in-flight stream aborts; its tab persists with `pi_session_path` |
| `GET /api/chat/config?runtime=pi` with empty `agent_runtime_options` table | no Pi rows seeded | Returns 200 with `{"models": [], "default_model": "", ...}`; frontend shows empty model dropdown + helpful message "No Pi models configured — see docs/IW_AI_Core_AI_Assistant_Models.md" |
| Project missing `ai_assistant.models` allowlist | F-00086's fail-open fallback for OpenCode | Same fallback for Pi: return full Pi model list from catalogue; warning log "ai_assistant.models not configured for project X — returning full Pi catalogue" |
| Sync of `agents/pi/extensions/` when `node_modules/` symlink target is broken | dangling symlink inside extension | `shutil.copytree` raises; sync engine catches and logs warning, continues with other extensions; counter increments only for successful copies; report in CLI output |

## Invariants

Conditions that **must hold true** after implementation. Each maps to a test.

1. **No Python built-in line iterator in `pi_jsonl_reader.py`** — grep proves the absence of `readline`, `for line in`, `iter(stream.readline, ...)` patterns. (`tests/unit/chat/test_pi_jsonl_reader.py::test_no_builtin_line_iterators_present`)
2. **Unicode separators inside JSON strings do not split records** — feeding a JSONL stream with ` `/` `/`` inside string values yields exactly one record per LF byte. (`tests/unit/chat/test_pi_jsonl_reader.py::test_unicode_separators_in_json_string_do_not_split`)
3. **`PiRuntime` implements `ChatRuntime` completely** — `PiRuntime.__abstractmethods__` is empty (constructible). (`tests/unit/chat/test_pi_runtime_abc_compliance.py`)
4. **MAX_PI_TABS cap is honoured by LRU eviction, never by rejection** — creating an arbitrary number of Pi tabs always succeeds; active-subprocess count is `min(active_tab_count, MAX_PI_TABS)`. (`tests/unit/chat/test_pi_runtime_lru_eviction.py`)
5. **Idle reaper kills only idle subprocesses** — a subprocess that received any event (in or out) within `IDLE_TIMEOUT_SECONDS` is NOT culled. (`tests/unit/chat/test_pi_runtime_idle_reaper.py`)
6. **`extension_ui_request` → `permission.asked` translation** preserves `id`, surfaces `tool`/`args`/`question`. (`tests/unit/chat/test_pi_event_normalization.py`)
7. **Allowlist extension is one-line** — `git diff orch/chat/tab_service.py` for the allowlist constant shows only `{"opencode"}` → `{"opencode", "pi"}` (no surrounding refactor). (`tests/unit/chat/test_tab_service_allowlist.py` — this test exists from F-00086; we extend it with a `runtime="pi"` case.)
8. **`pi_extensions_synced` counter increments on copy** — running sync_agents with a fixture `agents/pi/extensions/x/` produces `result.pi_extensions_synced == 1`. (`tests/unit/chat/test_sync_agents_extensions.py`)

## Dependencies

- **Depends on**: F-00086 (multi-tab AI Assistant on OpenCode — established the `ChatRuntime` ABC, `tab_service.ALLOWED_RUNTIMES`, the tab-scoped API, and the multi-tab UI that this Feature extends). F-00086 MUST be merged before F-00087 is executed.
- **Depends on**: CR-00062 (Pi as third agent runtime — established the `agents/pi/` master tree with 30 agent files, the `agent_runtime_options` rows for Pi, and the `pi -p` executor dispatch path). Already merged.
- **Blocks**: None.

## Impacted Paths

- `orch/chat/__init__.py`
- `orch/chat/pi/**`
- `orch/chat/tab_service.py`
- `orch/skills/sync_agents.py`
- `orch/cli/skills_commands.py`
- `dashboard/routers/chat.py`
- `dashboard/app.py`
- `dashboard/templates/chat_assistant/create_tab_modal.html`
- `dashboard/static/chat_assistant/chat.js`
- `agents/pi/extensions/**`
- `tests/unit/chat/test_pi_*.py`
- `tests/unit/chat/test_sync_agents_extensions.py`
- `tests/unit/chat/test_tab_service_allowlist.py`
- `tests/integration/test_chat_pi_*.py`
- `tests/integration/stubs/pi`
- `ai-dev/active/F-00087/**`

## TDD Approach

- **RED-first evidence** — S01 must capture targeted failing-test output before implementation:
  - `tests/unit/chat/test_pi_jsonl_reader.py::test_unicode_separators_in_json_string_do_not_split` — feeds a stream containing `{"text":"line1 line2"}\n` and asserts one record yielded. RED run fails with `ImportError: cannot import name 'aiter_jsonl_lines'` (module doesn't exist yet).
  - `tests/unit/chat/test_pi_runtime_lru_eviction.py::test_seventh_tab_evicts_lru` — creates 7 mock Pi clients; asserts 7th tab kills the LRU client. RED run fails with `ImportError` or `AttributeError`.

- **Unit tests** (S05):
  - `tests/unit/chat/test_pi_jsonl_reader.py` — Unicode separator regression (invariant #2), no-builtin-iterator grep (invariant #1), partial-line handling (incomplete record on stream close), `\r\n` line endings stripped to `\n`-only semantics.
  - `tests/unit/chat/test_pi_rpc_client.py` — command write encodes JSON + `\n`; event read decodes JSONL via the LF-only reader; `request_response` correlates by `id` and times out gracefully; `close()` graceful shutdown (SIGTERM then SIGKILL).
  - `tests/unit/chat/test_pi_runtime_lru_eviction.py` — LRU eviction at MAX_PI_TABS (invariant #4), evicted tab preserved in DB, respawn on activate.
  - `tests/unit/chat/test_pi_runtime_idle_reaper.py` — 15-min idle threshold (invariant #5), reaper task lifecycle (started in `__init__`, cancelled on `close()`), env-var override `IW_CORE_PI_IDLE_TIMEOUT`.
  - `tests/unit/chat/test_pi_runtime_abc_compliance.py` — invariant #3.
  - `tests/unit/chat/test_pi_event_normalization.py` — every Pi event type from §Scope mapping table → expected envelope (invariant #6); unknown events pass through.
  - `tests/unit/chat/test_sync_agents_extensions.py` — extension copy + counter + idempotency (invariant #8, AC7).
  - `tests/unit/chat/test_tab_service_allowlist.py` (extend existing) — `runtime="pi"` accepted (invariant #7).

- **Integration tests** (S05):
  - `tests/integration/test_chat_pi_mixed_tabs_independence.py` — uses stub `pi` binary on PATH (3-line bash: emits canned `agent_start`/`message_update`/`agent_end` JSONL events on stdout). Creates 1 OpenCode + 2 Pi tabs, drives prompts on each, asserts no event cross-contamination, asserts abort of one Pi tab does not affect the OpenCode tab or the other Pi tab.
  - `tests/integration/test_chat_pi_approval_flow.py` — stub `pi` binary + stub extension on the policy fixture. Simulates a `tool_call` matching an "ask" pattern; asserts the `extension_ui_request` event surfaces; POSTs approval; asserts the `extension_ui_response` is written to the subprocess stdin in the correct JSONL shape.
  - `tests/integration/test_chat_pi_lifecycle.py` — lazy spawn on first prompt; idle reaper kills subprocess after a shortened test timeout (1 second via env var override); reactivate spawns a fresh subprocess via `--session`.

- **Stub `pi` binary** (`tests/integration/stubs/pi`): 3-line bash script that reads JSONL commands from stdin, emits canned JSONL events on stdout per a simple decision table. Pattern lifted from CR-00062 S05. Marked executable via `chmod +x` in the test fixture setup; the test prepends `tests/integration/stubs/` to `PATH` for the duration of the test.

## Notes

- **R-00072 §2 — LF-only JSONL framing is the single biggest risk in this Feature.** Python's `io.IOBase.readline` and `for line in stream` split on Unicode separators (` `, ` `, ``) inside JSON strings; any tool output containing these characters will silently corrupt the protocol. The first unit test we write is the Unicode-separator regression; everything else builds on that being green. R-00072 §11 row "LF-only JSONL framing — Python defaults will break the protocol" is HIGH severity for a reason.
- **R-00072 §9 alternative considered + rejected: Node sidecar.** R-00072's recommended pattern for "if we pick Pi" was a Node sidecar wrapping the official SDK. We deliberately chose the RPC-subprocess-per-tab path because (a) it keeps the Python-only deployment story; (b) per-tab isolation maps naturally to per-subprocess isolation; (c) the LRU+idle pool bounds resource use; (d) it avoids a second runtime to deploy/monitor. The Node sidecar remains an option if RPC framing or the extension UI protocol proves more painful than estimated.
- **Approval UX parity is deliberate.** The Pi extension enriches `ctx.ui.confirm()` payload with `{tool, args, question}` so the existing F-00086 approval modal renders identically. The frontend has no idea (and needs none) whether the request originated from OpenCode's native `permission.asked` or Pi's `extension_ui_request` — that's the value of the event-normalization layer.
- **`browser_verification = true`** — Frontend changes the dropdown options. S13 captures pre-state of the OpenCode-only dropdown at execution time (the dropdown doesn't exist today — F-00086 creates it; F-00087 cannot pre-capture pre-state until F-00086 is merged).
- **`self_assess = true`** — Project `iw-ai-core` has `self_assess = true`; S14 (`self-assess-impl`) is the LAST step (after S13 qv-browser).
- **No projects.toml changes.** The chat panel reuses the existing `ai_assistant.models` per-project allowlist for both runtimes. If a project wants to restrict Pi models specifically, that's a follow-up (would add a `[projects.X.ai_assistant.pi]` sub-table).
- **MAX_PI_TABS = 6, configurable via env var.** Set `IW_CORE_MAX_PI_TABS=N` to override. Default chosen to leave headroom on a typical workstation while bounding worst-case memory/CPU. The OpenCode soft-cap (10) and the Pi LRU cap (6) are independent — total tabs across runtimes can exceed either bound.
- **IDLE_TIMEOUT_SECONDS = 900 (15 min), configurable via `IW_CORE_PI_IDLE_TIMEOUT`.** Keeps the lazy respawn UX comfortable while not pinning RAM for forgotten tabs.
- **Why not split into a separate Pipeline step for the TypeScript extension?** The extension is small (one file, ~100 lines) and its lifecycle is tightly coupled to the Python `PiRpcClient` (the extension's `ctx.ui.confirm` payload shape MUST match what the Python event normalizer expects). Keeping both in one Backend step avoids a serial cross-step dependency for ~100 lines of code. S02's code review covers both halves.
