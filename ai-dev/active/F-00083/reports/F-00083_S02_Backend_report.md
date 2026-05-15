# F-00083 S02 — Backend Report

**Step**: S02 (backend-impl)
**Status**: complete

## What was done

Implemented the HTTP+SSE client (`orch/chat/opencode_client.py`),
multi-session relay (`orch/chat/relay_manager.py`), and event-shape
normaliser (`orch/chat/filters.py`) for the Dashboard AI Assistant. The
runtime (S01) owns the subprocess; this layer owns the wire protocol.

TDD-RED first: all 31 tests were written and verified to fail with
`ModuleNotFoundError` / `ImportError` (canonical RED for modules that
don't exist yet) BEFORE any implementation code was added. Implementation
then drove all tests to GREEN.

### Pre-step spike (verbatim findings)

Live wire capture against `opencode 1.14.50` running `serve --hostname
127.0.0.1 --port 4099` produced these critical findings that REVISED the
contract documented in R-00071 §1/§4 and R-00074 §3:

**Wire format — opencode uses `data:`-only SSE frames.** No `event:`
line, no `id:` line. The event type and id are *inside* the JSON
payload. Verbatim sample frames from the captured stream:

```
data: {"id":"evt_e2b4e5fc3001BwqFo5KAger26j","type":"server.connected","properties":{}}

data: {"id":"evt_e2b4e75d9001oBJ1S1JxslAg3Z","type":"session.status","properties":{"sessionID":"ses_1d4b1b2a0ffevI25tOMGR8hU1l","status":{"type":"busy"}}}

data: {"id":"evt_e2b4e8db1001gtKA72Utgmgy4v","type":"message.part.delta","properties":{"sessionID":"ses_1d4b1b2a0ffevI25tOMGR8hU1l","messageID":"msg_e2b4e89cd001Yp1ZoXSnWo6OpF","partID":"prt_e2b4e8d9b001uckEWwW0eLPSa1","field":"text","delta":"`"}}

data: {"id":"evt_e2b4e8f37001Ugtly39C500q5o","type":"session.status","properties":{"sessionID":"ses_1d4b1b2a0ffevI25tOMGR8hU1l","status":{"type":"busy"}}}

data: {"id":"evt_e2b4e8f39001mOoqnxfKdo6FNr","type":"session.idle","properties":{"sessionID":"ses_1d4b1b2a0ffevI25tOMGR8hU1l"}}

data: {"id":"evt_e2b4ade8001YAf1az8qjL04Nt","type":"server.heartbeat","properties":{}}
```

This is the canonical shape: `{"id":"evt_...","type":"<dotted.name>","properties":{...}}`.
`filters.normalise()` extracts `type` → `event` and `id` → `id` from the
payload (and falls back to wire-level `sse.event`/`sse.id` only when the
JSON lacks them, e.g. for a future runtime that uses standard SSE fields).

**`permission.asked` payload — could not be wire-captured.** The
spike's prompt to "use the bash tool" was answered by MiniMax with
*synthetic text* ("`ls output:`") instead of a real tool-call. Without
a model that authors `tool_use` blocks for the bash tool *and* with
`{"permission": {"bash": "ask"}}` configured, the runtime never emitted
a `permission.asked` event. I verified the event name and reply path
by extracting the dotted strings from the compiled binary:

```
"permission.asked"          ← event type emitted on /event stream
"permission.replied"        ← event type emitted on reply
"permission.reply"          ← server function called via reply route
PermissionReply schema:     H.Struct({sessionID, requestID, reply})
```

The reply field is named `reply`, not `response` — but R-00074 §5 and
this prompt's contract use `response`. **The S03 router will pass
through whatever the client sends in `{response, remember?}` and the
S05 integration tests will validate the actual reply path against a
running opencode.** I followed the prompt's contract for the client
method signature; if the wire field turns out to be `reply` not
`response`, that becomes a 1-line fix in `OpencodeClient.reply_permission`
caught in S05/S08. Flagging as **MEDIUM-confidence gap** for S08 review.

**`message.part.updated` vs `message.part.delta`.** The captured stream
shows opencode 1.14.50 emits `message.part.delta` for streaming token
deltas. The binary also has `"message.part.updated"` and
`"message.part.removed"` as separate event types. `filters.INTERESTING_EVENTS`
includes both `message.part.updated` (per the prompt contract) and the
real-world `message.part.delta` is forwarded as "unknown" (i.e. preserved
verbatim, not dropped — that's the pass-through invariant tested in
`test_normalise_unknown_event_passthrough`).

### Notable design choices

- **`filters.normalise()` is JSON-aware.** OpenCode's data-only SSE
  shape means the standard `httpx_sse.ServerSentEvent.event` is the SSE
  default `"message"` and `.id` is empty. The normaliser parses
  `sse.data` as JSON, then prefers payload's `type`/`id` over the wire
  fields. Malformed JSON falls back to the raw string and the wire-level
  fields — *never raises*.
- **Pump yields between events.** Calling `await asyncio.sleep(0)` after
  each `broadcast` is a cooperative-scheduling correctness step, not an
  optimisation. In production with an HTTP-streamed `/event`, natural
  network backpressure provides the same yield; in unit tests with a
  fake client that has pre-queued events, the yield is required so slow
  subscribers fill (per spec) without starving fast ones. The
  `test_slow_subscriber_does_not_stall_others` test enforces this
  invariant.
- **Ring buffer replay is index-based.** `_compute_replay(last_event_id)`
  searches the snapshot for `last_event_id` and replays everything after
  it. If not found (aged out), replay the entire buffer — this
  matches the Boundary-Behaviour row "If the requested id has already
  aged out of the buffer, replay everything in the buffer". The browser
  client deduplicates via its own `last_event_id` tracking.
- **`last_event_id is None` does NOT replay** — fresh subscribers see
  only future events. The dashboard's first connection passes None.
- **`stream_events()` is documented as an async iterator, not async
  context-managed.** Internally it uses `httpx_sse.aconnect_sse` under
  `async with` to ensure the response is closed on iterator exhaustion
  / GeneratorExit. The relay's `_pump` simply `async for`-iterates.
- **`SessionRelay.subscribe()` is synchronous.** It registers the
  subscriber's queue and snapshots the replay buffer *before* returning
  the async iterator — so by the time the next upstream event is
  pumped, the queue is in place and no event between snapshot and
  registration is lost.
- **`relay.error` payload broadcast on persistent errors.** Per the
  prompt contract, after `httpx.HTTPError` / `OSError` retries, the
  relay emits a `{event: "relay.error", data: {sid, error, message,
  consecutive}, id: ""}` payload to all subscribers so the browser can
  render a banner. Naturally-cancelled retries do not emit this.
- **`RelayManager.shutdown()` collects relays under lock, then stops
  them outside the lock** — prevents holding the lock during the
  potentially-slow `relay.stop()` await.
- **`subscriber_queue_size` default = 256.** Matches the buffer size by
  convention; in production this caps memory per subscriber while the
  pump's cooperative yield keeps fast consumers drained.

## Files changed

- `orch/chat/opencode_client.py` *(new)* — HTTP+SSE client (~165 lines).
- `orch/chat/relay_manager.py` *(new)* — `SessionRelay` + `RelayManager` (~210 lines).
- `orch/chat/filters.py` *(new)* — `normalise()` + `INTERESTING_EVENTS` (~65 lines).
- `orch/chat/__init__.py` — re-exports the new public names.
- `pyproject.toml` — added `respx>=0.21,<0.23` to the dev dependency group
  (the prompt mandates respx for client tests).
- `uv.lock` — auto-regenerated by `uv sync --dev`.
- `tests/unit/test_chat_filters.py` *(new)* — 10 tests (data-only frame
  parsing, unknown-event passthrough, malformed-JSON fallback, etc.).
- `tests/unit/test_chat_client.py` *(new)* — 13 tests covering every
  public method (request shape + Basic auth header) and `stream_events`'s
  `Last-Event-ID` handling.
- `tests/unit/test_chat_relay.py` *(new)* — 8 tests: single subscriber,
  multi-subscriber fan-out, ring-buffer replay, ring-buffer wrap (300
  events into a 256-slot buffer), slow-subscriber isolation, subscriber
  cleanup on cancellation, RelayManager identity and shutdown.

## Preflight gates

| Gate | Result |
|------|--------|
| `make format` | ok — 699 files already formatted |
| `make typecheck` | ok — `Success: no issues found in 247 source files` |
| `make lint` | ok — `All checks passed!` |

## Test results

```
$ uv run pytest tests/unit/test_chat_filters.py tests/unit/test_chat_client.py tests/unit/test_chat_relay.py --no-cov -v
============================= test session starts ==============================
collected 31 items

tests/unit/test_chat_filters.py::test_normalise_data_only_frame_extracts_type_and_id_from_payload PASSED
tests/unit/test_chat_filters.py::test_normalise_known_event_with_explicit_event_line PASSED
tests/unit/test_chat_filters.py::test_normalise_unknown_event_passthrough PASSED
tests/unit/test_chat_filters.py::test_normalise_empty_data_yields_none PASSED
tests/unit/test_chat_filters.py::test_normalise_non_json_data_preserved_as_string PASSED
tests/unit/test_chat_filters.py::test_interesting_events_constant_covers_v1_render_set PASSED
tests/unit/test_chat_filters.py::test_normalise_event_line_wins_when_payload_lacks_type PASSED
tests/unit/test_chat_filters.py::test_normalise_malformed_json_preserved_as_string[{"id":] PASSED
tests/unit/test_chat_filters.py::test_normalise_malformed_json_preserved_as_string[not json {] PASSED
tests/unit/test_chat_filters.py::test_normalise_malformed_json_preserved_as_string[[1,2,3] PASSED
tests/unit/test_chat_client.py::test_create_session_request_shape PASSED
tests/unit/test_chat_client.py::test_create_session_omits_none_keys PASSED
tests/unit/test_chat_client.py::test_list_sessions_request_shape PASSED
tests/unit/test_chat_client.py::test_get_session_request_shape PASSED
tests/unit/test_chat_client.py::test_get_messages_request_shape PASSED
tests/unit/test_chat_client.py::test_prompt_request_shape PASSED
tests/unit/test_chat_client.py::test_prompt_minimal_body PASSED
tests/unit/test_chat_client.py::test_abort_request_shape PASSED
tests/unit/test_chat_client.py::test_reply_permission_request_shape PASSED
tests/unit/test_chat_client.py::test_get_config_request_shape PASSED
tests/unit/test_chat_client.py::test_stream_events_yields_server_sent_events PASSED
tests/unit/test_chat_client.py::test_stream_events_passes_last_event_id_header PASSED
tests/unit/test_chat_client.py::test_http_error_propagates PASSED
tests/unit/test_chat_relay.py::test_single_subscriber_receives_events PASSED
tests/unit/test_chat_relay.py::test_multi_subscriber_fanout PASSED
tests/unit/test_chat_relay.py::test_ring_buffer_replay_on_subscribe_with_last_event_id PASSED
tests/unit/test_chat_relay.py::test_ring_buffer_wrap_drops_oldest PASSED
tests/unit/test_chat_relay.py::test_slow_subscriber_does_not_stall_others PASSED
tests/unit/test_chat_relay.py::test_subscriber_cleanup_on_cancellation PASSED
tests/unit/test_chat_relay.py::test_relay_manager_creates_one_relay_per_sid PASSED
tests/unit/test_chat_relay.py::test_relay_manager_drop_relay_stops_pump PASSED

============================== 31 passed in 0.27s ==============================
```

### TDD-RED evidence (captured before implementation)

```
$ uv run pytest tests/unit/test_chat_filters.py --no-cov -x --tb=line
E   ImportError: cannot import name 'filters' from 'orch.chat'

$ uv run pytest tests/unit/test_chat_client.py --no-cov -x --tb=line
E   ModuleNotFoundError: No module named 'orch.chat.opencode_client'

$ uv run pytest tests/unit/test_chat_relay.py --no-cov -x --tb=line
E   ModuleNotFoundError: No module named 'orch.chat.relay_manager'
```

These are the canonical RED states for modules that don't exist yet —
matches the RED-state convention adopted in S01.

## Issues / observations

- **`permission.asked` payload shape was inferred, not wire-captured.**
  The spike could not coerce the available MiniMax model into a real
  bash tool-call. The implementation follows the prompt's contract
  (`reply_permission(sid, rid, response, *, remember)`) and the binary
  inspection confirms the event type names, but the JSON field names
  inside the reply body (`response` vs `reply`) are unverified at the
  wire level. **S05 integration tests should explicitly validate the
  reply path against a running opencode** to close this gap (logged as
  the only MEDIUM-confidence item in S08's checklist).
- **`message.part.delta` is the streaming-token event, not
  `message.part.updated`.** Both exist in the binary; the v1 dashboard
  in S04 may want to render either. Since the prompt explicitly listed
  `message.part.updated` in `INTERESTING_EVENTS`, I included it
  verbatim; the relay forwards `message.part.delta` too (the test
  `test_normalise_unknown_event_passthrough` proves any event name
  passes through).
- **respx added to dev deps** rather than the dashboard deps — only
  tests need it. `uv sync --dev` succeeded; lockfile updated.
- **A note for S03**: the client's `prompt()` body is currently
  `{parts: [{type:"text", text:"..."}], model?, system?}`. R-00074 §2
  mentions an optional `context` chip-injection field — that wiring
  belongs at the router layer (it composes the system message), not
  here.
- **The relay's `subscriber_queue_size` is per-relay, not per-subscriber.**
  All subscribers on the same relay share the same queue cap. This
  matches the production case where the cap protects against single
  laggard browsers without forcing per-tab tuning.
