# CR-00054_S04_Tests_prompt

**Work Item**: CR-00054 -- Add OpenCode stub to worktree E2E stack
**Step**: S04
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Same policy as S01. Tests use the in-process stub subprocess only — no docker calls.

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch migrations.

## Input Files

- `scripts/e2e_opencode_stub.py` — written by S01
- `orch/chat/opencode_client.py` — schema OpencodeClient expects from the stub
- `orch/chat/opencode_runtime.py` — `/global/health` polling contract
- `tests/integration/test_e2e_opencode_stub.py` — S01 created a minimal RED suite; this step expands it
- `tests/CLAUDE.md` — testing conventions (no live-DB, assertion strength)
- `skills/iw-ai-core-testing/SKILL.md` (or the project-local copy under `.claude/skills/`) — IW testing standards

## Output Files

- `tests/integration/test_e2e_opencode_stub.py` — expanded test suite
- `ai-dev/active/CR-00054/reports/CR-00054_S04_Tests_report.md` — step report

## Context

You are implementing **S04** — expanding the integration test suite for the stub so every endpoint, every event-sequence branch, and every auth path is covered.

## Requirements

### 1. Subprocess fixture

Add a session-scoped fixture that:
- Picks a free port via `socket.socket(...).bind(("127.0.0.1", 0)).getsockname()[1]`.
- Sets `OPENCODE_SERVER_PASSWORD=<random>` in the child env.
- Spawns `uv run python scripts/e2e_opencode_stub.py serve --hostname 127.0.0.1 --port <picked>` via `subprocess.Popen`.
- Polls `GET http://127.0.0.1:<picked>/global/health` until 200 (timeout 10 s).
- Yields `(base_url, password)`.
- On teardown: SIGTERM, wait 2 s, SIGKILL if still alive.

Optionally split into a function-scoped fixture if isolating per-test session state is needed.

### 2. Tests to add (minimum)

| Test name | Asserts |
|-----------|---------|
| `test_health_returns_200_unauthenticated` | `GET /global/health` returns 200 with no Authorization header |
| `test_basic_auth_required_on_protected_endpoints` | `GET /config` without auth returns 401; with wrong password returns 401; with right password returns 200 |
| `test_config_returns_models_array` | `/config` JSON has non-empty `models` list with required keys (`id`, `name`) and a non-empty `default_model` matching one of the models |
| `test_session_create_returns_id` | `POST /session` returns `{"id": "ses_..."}` matching `^ses_[0-9a-f]{8}$` |
| `test_session_list_returns_created_sessions` | After two `POST /session`, `GET /session` returns a list of length 2 in creation order |
| `test_session_get_unknown_returns_404` | `GET /session/nonexistent` returns 404 |
| `test_messages_empty_for_new_session` | `GET /session/{sid}/messages` returns `[]` immediately after create |
| `test_prompt_async_returns_200_then_event_stream_emits_sequence` | `POST /session/{sid}/prompt_async` returns 200; subscribing to `/event` shows `message.updated` → `message.updated` → `permission.asked` in order, all with monotonically increasing `id` values |
| `test_permissions_allow_resumes_stream` | After `permission.asked`, `POST /session/{sid}/permissions/{rid}` with `{"response": "allow"}` triggers a `message.updated` with `{tool_continued: true}` then `session.idle` |
| `test_permissions_deny_terminates_stream` | After `permission.asked`, `POST /session/{sid}/permissions/{rid}` with `{"response": "deny"}` triggers a `session.idle` with `{permission_denied: true}` |
| `test_abort_emits_session_idle_immediately` | `POST /session/{sid}/abort` causes the next event on `/event` to be `session.idle` with `{aborted: true}` |
| `test_last_event_id_replay_from_ring_buffer` | Connect, send a prompt, capture event id `K`; disconnect; reconnect with `Last-Event-ID: K`; receive only events with id `> K` |
| `test_ring_buffer_wraps_at_256` | Send 300 events; reconnect with `Last-Event-ID: 1`; receive at most 256 events |
| `test_invalid_argv_exits_with_code_2` | Invoke the stub with `--unknown-flag`; expect exit code 2 |
| `test_no_password_in_stub_stderr` | After driving traffic, the captured stderr from the subprocess must NOT contain the password substring (grep test) |

### 3. Use httpx + httpx_sse

For the JSON endpoints use `httpx.Client` with `auth=httpx.BasicAuth("opencode", password)`. For the SSE stream use `httpx_sse.connect_sse` (sync) or `aconnect_sse` (async) — your choice; mirror the pattern of `tests/unit/test_chat_client.py` if it exists (created in F-00083 S05).

### 4. Assertion strength

Per `tests/CLAUDE.md`:
- **Strong assertions**: every test must assert specific values, not "is truthy" or "is not None". Use `==` and equality comparisons over `assert x` patterns.
- **No vacuous tests**: `make test-assertions` will fail any test with fewer than 1 substantive `assert`.
- **Atomic**: each test verifies one behaviour, not a chain of seven things.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Apply this to the stub tests: don't settle for `assert "models" in body` — assert
`body["models"][0]["id"] == "stub/echo"`. Don't settle for `assert resp.status_code` —
compare `resp.status_code == 200`. Don't settle for "event arrived" — assert the
exact `event:` line and the relevant payload keys/values you expect.

### 5. Cross-project isolation

Per `tests/CLAUDE.md`, never write to the live DB and never call orch DB session helpers. The stub is standalone; tests should only touch `tests/integration/test_e2e_opencode_stub.py` and the new fixture.

## Project Conventions

Read `tests/CLAUDE.md` for fixture conventions, test layout, and the live-DB write guard.

## TDD Requirement

The behaviours under test exist (S01 implemented them). For each new assertion, add the test first, run it to confirm GREEN (because S01 already implemented the behaviour). If you find a test that goes RED, that is a bug in S01 — file it in `notes` and fix S01 (S07 cycle if necessary; do NOT silently weaken the test).

For `tdd_red_evidence`: pick one new test that you initially expected to pass but went RED (a real bug found) OR `"n/a — extending existing GREEN tests for coverage, no new behaviour under test"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Run only the test file you wrote:

```bash
uv run pytest tests/integration/test_e2e_opencode_stub.py -v
```

Do NOT run `make test-integration` — that is S15's job.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "tests-impl",
  "work_item": "CR-00054",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/integration/test_e2e_opencode_stub.py"],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — extending S01's GREEN tests with full coverage",
  "blockers": [],
  "notes": ""
}
```
