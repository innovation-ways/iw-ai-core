# F-00083_S03_API_prompt

**Work Item**: F-00083 -- Dashboard AI Assistant — OpenCode-backed chat panel (v1)
**Step**: S03
**Agent**: api-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migrations.)

## Input Files

- `ai-dev/active/F-00083/F-00083_Feature_Design.md` — Design (Sections: API Changes, AC1–AC10, Boundary Behavior)
- `ai-dev/work/F-00083/reports/F-00083_S01_Backend_report.md` — S01 report
- `ai-dev/work/F-00083/reports/F-00083_S02_Backend_report.md` — S02 report (with captured `permission.asked` payload if available)
- `dashboard/routers/sse.py` — **the canonical SSE shape to mirror**; copy its generator structure, the headers, and the disconnect check
- `dashboard/routers/code_qa.py` — secondary pattern for thread-to-queue async work
- `dashboard/app.py` — lifespan + router registration to extend

## Output Files

- `ai-dev/work/F-00083/reports/F-00083_S03_API_report.md`
- `dashboard/routers/chat.py` (new — 8 endpoints)
- `dashboard/app.py` (modified — lifespan start/stop of `OpencodeRuntime`, register the new router)
- `tests/dashboard/test_chat_router.py` (new — FastAPI `TestClient` tests with mocked `OpencodeClient`)

## Context

You are implementing the dashboard's HTTP face for the chat. The router holds singleton instances of `OpencodeRuntime`, `OpencodeClient`, and `RelayManager` via FastAPI dependencies. The runtime is started in `dashboard/app.py`'s `_lifespan` before existing daemon startup; stopped on shutdown.

## Requirements

### 1. `dashboard/routers/chat.py`

Implement 8 endpoints. Match `dashboard/routers/sse.py` shape exactly for the SSE stream — same headers (`Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`), same disconnect check via `request.is_disconnected()`, same 30 s keep-alive ping pattern.

| Method | Path | Body / Query | Returns |
|--------|------|--------------|---------|
| POST | `/api/chat/sessions` | `{model?, agent?, directory?}` | `{session_id}` |
| GET | `/api/chat/sessions` | — | `[{id, created_at, title?}]` (passthrough from OpenCode) |
| GET | `/api/chat/sessions/{sid}` | — | `{session: {...}, messages: [...]}` |
| GET | `/api/chat/sessions/{sid}/stream` | `Last-Event-ID` header | SSE stream (`event: …`, `data: …`, `id: …`) — relays from `RelayManager.get_or_create_relay(sid).subscribe(...)` |
| POST | `/api/chat/sessions/{sid}/prompt` | `{text, model?, context?}` | `204` |
| POST | `/api/chat/sessions/{sid}/abort` | — | `204` |
| POST | `/api/chat/sessions/{sid}/permissions/{rid}` | `{response, remember?}` | `204` |
| GET | `/api/chat/config` | — | `{models: [...], default_model, default_agent}` |
| GET | `/api/chat/skills` | — | `[{kind: "skill"\|"command", name, description}]` |

Implementation notes:

- The `context` field on `POST /prompt` is the "Currently viewing X" chip payload (`{type, id, title}`). When present, prepend a short `[Context: viewing {title} ({type} {id})]` to the prompt's first text part — implementer's call whether to thread through OpenCode's `system` field instead. Pick one and document it.
- **Caching** for `/api/chat/config` and `/api/chat/skills` — TTL 30 s. For `/api/chat/skills`, also stat the `.opencode/skills/` and `.opencode/commands/` directories and invalidate the cache on mtime change. Simple in-memory cache; no Redis.
- **Errors**: if the runtime is unhealthy (`runtime.health()` returns False), return `503 {"error": "OpenCode runtime unavailable"}` from every endpoint except `/api/chat/config` (which still returns its cached value if any).
- **Auth**: the dashboard doesn't have user auth (single-user). However, the OpenCode HTTP server is bound to 127.0.0.1 and the password is process-memory only — never leaks to the client. The dashboard endpoints themselves do NOT pass through Basic auth; they translate from public endpoints to internal authenticated calls.

### 2. `dashboard/app.py` lifespan

In `_lifespan`, before the existing daemon-startup block, add:

```python
runtime = OpencodeRuntime(repo_root=..., port=cfg.opencode_port, bin_path=cfg.opencode_bin)
await runtime.start()
client = OpencodeClient(base_url=runtime.base_url, password=runtime.password)
relay_manager = RelayManager(client)
app.state.opencode_runtime = runtime
app.state.opencode_client = client
app.state.relay_manager = relay_manager
```

On shutdown, in reverse order: `await relay_manager.shutdown()` → `await runtime.stop()`. Wrap in try/except so a runtime failure during startup is logged but does NOT crash the dashboard — set `app.state.opencode_runtime = None` and the router endpoints return 503.

Register the new router after `sse.py`'s router and before any catch-all 404 handler.

### 3. Tests (`tests/dashboard/test_chat_router.py`)

Use FastAPI `TestClient`. Mock `OpencodeClient` so the dashboard tests are hermetic.

Test cases:
- `test_create_session_returns_session_id` — mocks `client.create_session` to return `"sess-1"`; assert `POST /api/chat/sessions` returns `{"session_id": "sess-1"}`.
- `test_runtime_unavailable_returns_503` — set `app.state.opencode_runtime = None`; assert all endpoints except `/config` return 503.
- `test_config_cache_30s` — first request hits `client.get_config()`; second within 30 s does NOT.
- `test_skills_cache_invalidates_on_mtime_change` — touch `.opencode/skills/dummy/SKILL.md`; next request hits the filesystem walk.
- `test_stream_endpoint_forwards_relay_events` — fake relay yields three payloads; assert SSE response contains three `event:` lines and the keep-alive header set.
- `test_stream_endpoint_passes_last_event_id` — request with `Last-Event-ID` header; assert relay's `subscribe(last_event_id=...)` is called with that value.
- `test_prompt_with_context_chip_threaded` — POST `/prompt` with `context` field; assert mocked `client.prompt(...)` was called with the chip metadata threaded into either the prompt text or the system field (whichever convention was chosen — assert that convention).
- `test_permission_reply_forwards` — POST to `/permissions/{rid}` forwards the body to `client.reply_permission(sid, rid, ...)`.

NO live OpenCode binary in the test path — fully mocked.

## Project Conventions

Read `dashboard/CLAUDE.md`:
- Routers are thin (validation + delegation only).
- htmx POSTs to `/actions/*` (work-item-scoped) or `/api/...` (resource-scoped) return HTML fragments. **For the chat router, every endpoint returns JSON or SSE** — we are NOT serving htmx fragments here; the chat UI is a custom EventSource client in `chat.js`.
- Tailwind CSS is prebuilt; this step does not touch CSS.
- Use `dependencies.py:get_db()` if any endpoint needs a DB session (the chat router shouldn't need it — no new tables).

Mirror the SSE-generator shape from `dashboard/routers/sse.py` lines 170–278 — that pattern is the project-canonical answer.

## TDD Requirement

RED-first per template. `tdd_red_evidence` must be a real test failure before the router is implemented.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

Targeted: `uv run pytest tests/dashboard/test_chat_router.py -v`. Do NOT run `make test-unit` or `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "api-impl",
  "work_item": "F-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/chat.py",
    "dashboard/app.py",
    "tests/dashboard/test_chat_router.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "8 passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_chat_router.py::test_create_session_returns_session_id — ModuleNotFoundError or 404 (captured before implementation)",
  "blockers": [],
  "notes": "Context-chip threading convention chosen: {prompt-prepend|system-field}. Cache TTL: 30s. Lifespan failure mode: tested (503 on all endpoints)."
}
```
