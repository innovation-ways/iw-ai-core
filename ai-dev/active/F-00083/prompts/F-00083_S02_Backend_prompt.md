# F-00083_S02_Backend_prompt

**Work Item**: F-00083 -- Dashboard AI Assistant — OpenCode-backed chat panel (v1)
**Step**: S02
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migrations.)

## Input Files

- `ai-dev/active/F-00083/F-00083_Feature_Design.md` — Design (Boundary Behavior rows on tab refresh, mid-stream disconnect, ring-buffer wrap)
- `ai-dev/work/F-00083/reports/F-00083_S01_Backend_report.md` — S01 report (confirms `OpencodeRuntime` exists)
- `docs/research/R-00071-opencode-dashboard-embedding.md` §1, §5 — endpoint list + SSE bus event vocabulary
- `docs/research/R-00074-minimal-v1-dashboard-chat.md` §2, §3 — client + relay sketch
- `dashboard/routers/sse.py` — canonical event-generator pattern (mirror its `event:`/`data:`/`id:` lines + 30 s keep-alive)
- `dashboard/routers/code_qa.py` — canonical thread-to-async-queue pattern

## Output Files

- `ai-dev/work/F-00083/reports/F-00083_S02_Backend_report.md`
- `orch/chat/opencode_client.py` (new)
- `orch/chat/relay_manager.py` (new)
- `orch/chat/filters.py` (new)
- `tests/unit/test_chat_client.py` (new — TDD-RED, uses `respx`)
- `tests/unit/test_chat_relay.py` (new — TDD-RED)
- `tests/unit/test_chat_filters.py` (new — TDD-RED)

## Context

You are implementing the **HTTP+SSE client** and the **multi-session relay**. The runtime owns the subprocess; this layer owns the wire protocol.

## Pre-step Spike (≤5 minutes — DO THIS FIRST)

Before writing any test or implementation code, run a wire-capture spike:

1. Start `opencode serve --hostname 127.0.0.1 --port 4099` in a scratch terminal with `OPENCODE_SERVER_PASSWORD=test`.
2. Configure `.opencode/config.json` (in a scratch dir) with `{"permission": {"bash": "ask"}}`.
3. Create a session: `curl -u opencode:test -X POST http://127.0.0.1:4099/session`.
4. Subscribe to events: `curl -u opencode:test -N http://127.0.0.1:4099/event &`.
5. Send a prompt that will trigger a bash call: `curl -u opencode:test -X POST http://127.0.0.1:4099/session/<sid>/prompt_async -H 'content-type: application/json' -d '{"parts":[{"type":"text","text":"run ls"}]}'`.
6. Capture the actual `permission.asked` SSE event from the stream — record its full JSON payload in your S02 step report as a verbatim block.
7. Adjust the event-shape contract in `filters.py` to the real payload before completing this step.

If the spike is impossible (no `opencode` binary in the worktree), document this in the report and proceed using the documented shape from R-00071 §4 — flag this as a MEDIUM-confidence gap for S08 review.

## Requirements

### 1. `orch/chat/opencode_client.py`

```python
class OpencodeClient:
    def __init__(self, base_url: str, password: str, username: str = "opencode") -> None: ...

    async def create_session(self, *, model: str | None = None, agent: str | None = None,
                             directory: str | None = None) -> str: ...
    async def list_sessions(self) -> list[dict]: ...
    async def get_session(self, sid: str) -> dict: ...
    async def get_messages(self, sid: str) -> list[dict]: ...
    async def prompt(self, sid: str, text: str, *, model: str | None = None,
                     system: str | None = None) -> None: ...
    async def abort(self, sid: str) -> None: ...
    async def reply_permission(self, sid: str, rid: str, response: str,
                               *, remember: bool = False) -> None: ...
    async def get_config(self) -> dict: ...

    async def stream_events(self, *, last_event_id: str | None = None) -> AsyncIterator[ServerSentEvent]:
        """yield from httpx_sse.aconnect_sse(...) with Last-Event-ID header if provided."""
```

Use `httpx.AsyncClient(base_url=..., auth=httpx.BasicAuth(...), timeout=None)`. The `stream_events` method is async-iterable and yields `httpx_sse.ServerSentEvent` instances (the relay reads `.event`, `.data`, `.id`).

Errors propagate (don't swallow). Caller wraps.

### 2. `orch/chat/relay_manager.py`

```python
class SessionRelay:
    def __init__(self, client: OpencodeClient, sid: str, buffer_size: int = 256) -> None: ...
    async def start(self) -> None: ...      # spawns the upstream-pump task
    async def stop(self) -> None: ...
    async def subscribe(self, last_event_id: str | None = None) -> AsyncIterator[dict]:
        """Yield normalised {event, data, id} payloads. On entry, replay from ring buffer
        any events with id > last_event_id; then yield new ones as the upstream pump
        produces them. Cleans up the subscriber queue on cancellation."""

class RelayManager:
    def __init__(self, client: OpencodeClient) -> None: ...
    async def get_or_create_relay(self, sid: str) -> SessionRelay: ...
    async def drop_relay(self, sid: str) -> None: ...
    async def shutdown(self) -> None: ...
```

Ring buffer = `collections.deque(maxlen=256)`. Each upstream event from `client.stream_events()` is normalised via `filters.normalise(...)` to `{event, data, id}`, appended to the deque, and `put_nowait`-broadcast to every subscriber queue. If a subscriber queue is full (`asyncio.QueueFull`), drop the event for that subscriber and log WARN with the subscriber's id — never let one slow subscriber stall the others.

The upstream pump runs as a single `asyncio.Task` per `SessionRelay`. On `httpx.ReadError`, log INFO and retry `client.stream_events(last_event_id=<last seen>)` with backoff 300 ms → 3 s, capped. If the runtime returns persistent errors, log ERROR and surface via a special `{event: "relay.error", data: {...}}` payload to subscribers.

### 3. `orch/chat/filters.py`

A pure function `normalise(sse: ServerSentEvent) -> dict` that returns `{"event": sse.event, "data": json.loads(sse.data) if sse.data else None, "id": sse.id}`. Unknown event types are passed through verbatim — do NOT drop. Also a constant list `INTERESTING_EVENTS` documenting the events the dashboard renders (`message.part.updated`, `tool.execute.before`, `tool.execute.after`, `permission.asked`, `permission.replied`, `session.idle`, `session.updated`, `session.error`).

### 4. TDD-RED tests

`tests/unit/test_chat_client.py` (with `respx`):
- `test_create_session_request_shape` — assert `respx` saw a POST to `/session` with the JSON body and `Basic` auth header.
- One test per public method: shape + auth.
- `test_stream_events_passes_last_event_id_header` — assert the GET to `/event` includes `Last-Event-ID: <value>` when provided.

`tests/unit/test_chat_relay.py`:
- `test_single_subscriber_receives_events` — feed three fake SSEs upstream, assert subscriber yields three normalised payloads.
- `test_multi_subscriber_fanout` — two subscribers, both receive all events.
- `test_ring_buffer_replay_on_subscribe_with_last_event_id` — push 10 events with ids 1–10; new subscriber with `last_event_id="5"` receives events with id > 5 from the buffer immediately.
- `test_ring_buffer_wrap_drops_oldest` — push 300 events (buffer maxlen=256); assert the oldest 44 are gone.
- `test_slow_subscriber_does_not_stall_others` — one subscriber whose queue is artificially full; other subscriber still receives.
- `test_subscriber_cleanup_on_cancellation` — cancel a subscriber's iteration; assert the relay's subscriber list shrinks.

`tests/unit/test_chat_filters.py`:
- `test_normalise_known_event` — input SSE with `event="message.part.updated"`, JSON data; assert dict shape.
- `test_normalise_unknown_event_passthrough` — input SSE with `event="some.future.event"`; assert it still produces `{event: "some.future.event", data: ..., id: ...}`.

**RED phase**: each test file must show `AttributeError`/`AssertionError`/`NotImplementedError` failures before the module is implemented. Capture for `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

Targeted: the three new test files. Do NOT run `make test-unit`.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "backend-impl",
  "work_item": "F-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/chat/opencode_client.py",
    "orch/chat/relay_manager.py",
    "orch/chat/filters.py",
    "tests/unit/test_chat_client.py",
    "tests/unit/test_chat_relay.py",
    "tests/unit/test_chat_filters.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (across 3 files)",
  "tdd_red_evidence": "tests/unit/test_chat_relay.py::test_ring_buffer_wrap_drops_oldest — AssertionError: assert 0 == 256 (captured before implementation)",
  "blockers": [],
  "notes": "Pre-step spike: {captured permission.asked payload | skipped because opencode binary unavailable; using documented shape}. Verbatim payload (if captured) is included as a fenced block in this report."
}
```
