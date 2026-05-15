# F-00083_S05_Tests_prompt

**Work Item**: F-00083 -- Dashboard AI Assistant — OpenCode-backed chat panel (v1)
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migrations.)

## Input Files

- `ai-dev/active/F-00083/F-00083_Feature_Design.md` — Design (Boundary Behavior; TDD Approach; AC1–AC10)
- All prior step reports under `ai-dev/work/F-00083/reports/`
- `tests/CLAUDE.md` — testcontainer/sqlite-memory conventions, FTS trigger rules, no-live-DB rule
- Existing tests for shape reference: `tests/unit/test_*` and `tests/integration/test_*`

## Output Files

- `ai-dev/work/F-00083/reports/F-00083_S05_Tests_report.md`
- `tests/integration/test_chat_endpoint_session_lifecycle.py` (new)
- `tests/integration/test_chat_endpoint_permission_flow.py` (new)
- `tests/integration/test_chat_endpoint_reconnect.py` (new)
- Any test-fixture additions in `tests/conftest.py` or a local `tests/integration/conftest.py` (only if needed)

## Context

S01/S02 already added the unit tests for runtime/client/relay/filters. S03 already added FastAPI `TestClient` tests for the router. **This step adds the integration tests** that exercise the full happy path through the relay + router with realistic event streams. NO live OpenCode binary requirement — use a minimal fake SSE server fixture that mimics OpenCode's event vocabulary (a Starlette/FastAPI test app or `respx`-style server).

## ⚠️ Semantic Correctness Warning (I003 lesson)

A passing test that asserts the **wrong thing** is worse than no test — it gives false confidence. Every test you write here must be **semantically meaningful**:

- **Assert on observable values, not on "no exception raised."** A test that only checks `response.status_code == 200` and never inspects the body or the downstream effect is a vacuous test. The `make test-assertions` QV gate (S11) will flag these.
- **Prove the test exercises the path under test.** Before declaring done, *temporarily* mutate the production code to break the behaviour the test claims to cover and confirm the test fails. If it still passes, the test is checking the wrong thing — fix it before reverting. (Do this in your local checkout only — the prompt does NOT require committing the broken state.)
- **For SSE / relay tests, assert on event ordering, ids, and payload shape** — not just "some bytes arrived." For permission-flow tests, assert the upstream fake server actually received the reply with the right `response` value.
- **For reconnect tests with `Last-Event-ID`, assert which specific events were replayed**, not just that *something* was returned.

If you find a test that's hard to make semantically meaningful, that's usually a sign the production code's contract is too weak to test — surface it as a finding in the step report, not as a watered-down test.

## Requirements

### 1. `tests/integration/test_chat_endpoint_session_lifecycle.py`

Cover the full happy path of AC2 (prompt → stream → approval → abort) at the dashboard level:

- `test_session_lifecycle_create_prompt_stream_abort` — POST `/api/chat/sessions`, get sid; POST `/api/chat/sessions/{sid}/prompt`; GET `/api/chat/sessions/{sid}/stream` and consume 3+ SSE events; POST `/api/chat/sessions/{sid}/abort`; assert clean shutdown.
- `test_concurrent_sessions_independent_streams` — Create two sessions, prompt each, consume their streams in parallel, assert event ids don't interleave between sessions.

### 2. `tests/integration/test_chat_endpoint_permission_flow.py`

Cover AC2's approval/deny path:

- `test_permission_asked_event_renders_and_reply_forwards` — fake SSE server emits a synthetic `permission.asked` event; dashboard `/api/chat/sessions/{sid}/stream` forwards it; client POSTs `/permissions/{rid}` with `{response: "allow"}`; assert the fake server received the reply.
- `test_permission_deny_blocks_tool` — same shape with `{response: "deny"}`; assert the deny was forwarded and the fake emits `permission.replied` with the deny value.

### 3. `tests/integration/test_chat_endpoint_reconnect.py`

Cover AC6 (tab-refresh reconnect):

- `test_reconnect_replays_buffered_events_via_last_event_id` — first subscriber consumes events 1–10; disconnect; second subscriber connects with `Last-Event-ID: 5`; assert it receives events 6–10 from the ring buffer.
- `test_reconnect_past_ring_buffer_emits_gap_warning` — fake server has emitted 300 events (buffer maxlen=256); reconnect with `Last-Event-ID: 1`; assert client receives the most recent 256 events PLUS a special `event: gap` warning payload.

### 4. Fixture conventions

- Fake SSE server: a small `pytest` fixture that spawns an in-process Starlette app on a random port; emits a programmable sequence of SSE events on `GET /event`; accepts inbound POSTs.
- Configure the dashboard's `OpencodeClient` to point at the fake server's base_url (override via dependency-injection in the test).
- Per `tests/CLAUDE.md`: testcontainer Postgres only (no sqlite-in-memory); even though this test does no DB work, the dashboard's lifespan touches the DB on startup — keep the existing testcontainer pattern.

### 5. Verify everything

```bash
uv run pytest \
  tests/integration/test_chat_endpoint_session_lifecycle.py \
  tests/integration/test_chat_endpoint_permission_flow.py \
  tests/integration/test_chat_endpoint_reconnect.py \
  -v
```

Do NOT run `make test-integration` (S15 QV gate).

## Project Conventions

`tests/CLAUDE.md`:
- **NEVER** connect tests to the live DB (port 5433); testcontainer only.
- **MUST** replace `postgresql+psycopg2://` with `postgresql+psycopg://` on testcontainer URLs.
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- **NEVER** `importlib.reload(orch.config)` — use `monkeypatch.delenv()` instead.

## TDD Requirement

This is a `tests-impl` step — exempt from strict RED-first per the standard prompt template. Use `tdd_red_evidence: "n/a — tests-impl step, code already in place per S01–S04"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

Targeted only — the three new files.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "F-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_chat_endpoint_session_lifecycle.py",
    "tests/integration/test_chat_endpoint_permission_flow.py",
    "tests/integration/test_chat_endpoint_reconnect.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (across 3 files)",
  "tdd_red_evidence": "n/a — tests-impl step, code already in place per S01–S04",
  "blockers": [],
  "notes": "Fake SSE server fixture in tests/integration/conftest.py (if added). Boundary-row coverage map: documented in the report."
}
```
