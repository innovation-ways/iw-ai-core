# CR-00054_S01_Pipeline_prompt

**Work Item**: CR-00054 -- Add OpenCode stub to worktree E2E stack
**Step**: S01
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers spun up by pytest fixtures; read-only introspection (`docker ps`, `docker inspect`, `docker logs`); `./ai-core.sh` and `make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orchestration DB. This step does NOT touch migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00054 --json`
- `ai-dev/active/CR-00054/CR-00054_CR_Design.md` — design document
- `scripts/e2e_ollama_stub.py` — canonical stub pattern to follow
- `orch/chat/opencode_runtime.py` — what the stub must satisfy (OpencodeRuntime probes)
- `orch/chat/opencode_client.py` — JSON shapes the stub must return
- `dashboard/routers/chat.py` — endpoints that consume OpencodeClient's responses
- F-00083 design doc and reports (already merged): `ai-dev/archive/F-00083/**` if present, else the implementation in `orch/chat/*` and `dashboard/routers/chat.py`

## Output Files

- `scripts/e2e_opencode_stub.py` — the stub server
- `ai-dev/active/CR-00054/reports/CR-00054_S01_Pipeline_report.md` — step report

## Context

You are implementing **S01** of CR-00054 — the new `scripts/e2e_opencode_stub.py` that mimics `opencode serve` v1.15.0's HTTP+SSE wire protocol just well enough to satisfy `orch/chat/OpencodeRuntime` + `OpencodeClient` and the dashboard's chat router.

Read `CR-00054_CR_Design.md` §"Desired Behavior" for the full endpoint list and event-sequence contract. The canonical pattern to follow is `scripts/e2e_ollama_stub.py` (488 lines; Starlette / FastAPI server, `--port` CLI flag, deterministic responses).

## Requirements

### 1. CLI entry point

Accept the exact invocation `opencode serve --hostname H --port N` (the form OpencodeRuntime uses in `_spawn_once`). Implement via `argparse` with a `serve` subcommand or a single positional gate. Any other argv form should `sys.exit(2)` with a usage message. Default hostname `127.0.0.1`, default port `4096`.

**Also implement `opencode --selftest`** — a no-network, no-port-bind mode that imports the FastAPI/Starlette app, runs a one-line `assert` (e.g. `assert hasattr(app, "routes")`), and exits 0. S02's Dockerfile build-time validation depends on this — do NOT skip it. The selftest must NOT require `OPENCODE_SERVER_PASSWORD` to be set (provide a deterministic fallback when missing in selftest mode only). The selftest path is purely for build-time smoke; never enable it implicitly under `serve`.

### 2. HTTP Basic auth

Read `OPENCODE_SERVER_PASSWORD` from env at startup. Reject any request whose `Authorization: Basic ...` header does not decode to `opencode:<that password>` with `401`. **Exception**: `GET /global/health` is accepted with or without an Authorization header (OpencodeRuntime's `httpx.AsyncClient` always carries Basic auth — see `orch/chat/opencode_runtime.py:103-110, :213-225` — but the stub does NOT validate it on this path, so the stub stays forgiving). Never log the password.

### 3. HTTP endpoints

Implement these endpoints with the shapes below. JSON content type. All must respond within 100 ms (they are synchronous in-memory operations).

| Method | Path | Behaviour |
|--------|------|-----------|
| GET | `/global/health` | `200 ""` (empty body). Unauthenticated. |
| GET | `/config` | `200 {"models": [{"id": "stub/echo", "name": "Stub Echo"}], "default_model": "stub/echo", "default_agent": "build"}` |
| POST | `/session` | Body may be empty or `{model?, agent?, directory?}`. Returns `{"id": "ses_<8-hex>", "created_at": "<iso-8601>", "title": null}`. Stores the session in a process-local dict. |
| GET | `/session` | Returns a list of all created sessions (most recent last). |
| GET | `/session/{sid}` | Returns the stored session dict; `404` if unknown. |
| GET | `/session/{sid}/messages` | Returns a list of message dicts (empty for a new session, growing as `prompt_async` synthesises assistant turns). |
| POST | `/session/{sid}/prompt_async` | Body `{parts: [{type: "text", text: "..."}], model?, system?}`. Returns `200 {}` immediately. Synchronously enqueue the deterministic event sequence onto the `/event` stream (see §4). `404` if session unknown. |
| POST | `/session/{sid}/abort` | Returns `200 {}`. Emits a `session.idle` event with `{aborted: true}` immediately. |
| POST | `/session/{sid}/permissions/{rid}` | Body `{response: "allow"\|"deny", remember?: bool}`. Returns `200 {}`. If `rid` matches the most-recent synthetic `permission.asked` event for the session, emit one final `message.updated` with `{tool_continued: true}` (allow) or `{tool_blocked: true}` (deny). |

### 4. `/event` SSE stream

`GET /event` — long-lived `text/event-stream`. Honour `Last-Event-ID` request header for replay from a per-process ring buffer (`collections.deque(maxlen=256)`). Each event frame MUST include an `id:` line so the relay can resume.

Deterministic synthetic sequence emitted on `POST /session/{sid}/prompt_async`:

1. `event: message.updated\ndata: {"session_id": "<sid>", "role": "assistant", "status": "streaming", "text": ""}\nid: <auto-incr>`
2. `event: message.updated\ndata: {"session_id": "<sid>", "role": "assistant", "status": "streaming", "text": "ok — running ls"}\nid: <auto-incr>`
3. `event: permission.asked\ndata: {"session_id": "<sid>", "request_id": "req_<8-hex>", "tool": "bash", "command": "ls -la"}\nid: <auto-incr>`
4. **Pause** until either the client sends `POST /session/{sid}/permissions/{rid}` (allow/deny) OR 2 s elapse (timeout → emit `session.idle` with `{permission_timeout: true}`).
5. If allow: `event: message.updated\ndata: {"session_id": "<sid>", "role": "assistant", "status": "complete", "text": "ok — running ls\nCONTENTS"}\nid: <auto-incr>` followed by `event: session.idle\ndata: {"session_id": "<sid>"}\nid: <auto-incr>`.
6. If deny: `event: session.idle\ndata: {"session_id": "<sid>", "permission_denied": true}\nid: <auto-incr>`.

Use `asyncio` tasks + an `asyncio.Queue` per subscriber. When a subscriber connects, replay missed events from the ring buffer (those with `id > Last-Event-ID`) before streaming new ones.

### 5. TDD-RED first

Write `tests/integration/test_e2e_opencode_stub.py` (one test file; S04's tests-impl step will expand it). Confirm targeted RED run, capture the failing line(s) for `tdd_red_evidence` in your report. Then implement the stub until green.

For S01's RED run, the minimal failing tests are:

- `test_health_returns_200` — direct `requests.get` to `/global/health`.
- `test_config_endpoint_returns_models_array` — `/config` shape.
- `test_basic_auth_required` — 401 without auth.
- `test_session_lifecycle_create_get_list` — POST `/session` then GET.

S04 expands to the full integration suite.

### 6. Implementation conventions

- Use `fastapi.FastAPI` (already a project dependency via the dashboard). The stub is structurally similar to `scripts/e2e_ollama_stub.py`; mirror its style.
- Use `uv run python scripts/e2e_opencode_stub.py serve --port N --hostname H` — invoked through `uv run` so it inherits the project venv.
- All state is in-process; no DB, no disk. Process exits cleanly on SIGTERM.
- Logging via `logging.getLogger(__name__)` at INFO. **Never** log the password, even at DEBUG.
- No new external dependencies. `fastapi` + `uvicorn` + `httpx` are already pinned.

## Project Conventions

Read `CLAUDE.md`. Key points for this step:

- Use `uv run` for any Python invocation.
- The stub is **not** an orch module; do not import from `orch.*`. Keep it standalone so the e2e image doesn't need the full orch package at runtime.
- Type-check your additions: `make type-check` must pass for `scripts/e2e_opencode_stub.py`.

## TDD Requirement

Follow TDD (Red-Green-Refactor) — see template's standard TDD section. Confirm the failure is for the expected reason (AssertionError or ImportError because the module doesn't exist yet), not a fixture / collection error.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:
1. `make format` (must report ok or fixed)
2. `make typecheck` (zero errors on touched files)
3. `make lint` (zero errors)

## Test Verification (NON-NEGOTIABLE)

Run only the test file(s) you wrote or modified in this step:

```bash
uv run pytest tests/integration/test_e2e_opencode_stub.py -v
```

Do NOT run `make test-integration` — that is S15's job.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "pipeline-impl",
  "work_item": "CR-00054",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "scripts/e2e_opencode_stub.py",
    "tests/integration/test_e2e_opencode_stub.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/integration/test_e2e_opencode_stub.py::test_health_returns_200 — ModuleNotFoundError or ConnectionRefusedError",
  "blockers": [],
  "notes": ""
}
```
