# CR-00067_S01_Backend_prompt

**Work Item**: CR-00067 — AI Assistant — Context Usage Percentage Indicator
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step writes no migrations. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00067 --json`
- `ai-dev/active/CR-00067/CR-00067_CR_Design.md` — Design document
- `orch/CLAUDE.md` · `tests/CLAUDE.md` — package + test conventions
- `skills/iw-ai-core-testing/SKILL.md` — **read before writing any test**
- `dashboard/routers/chat.py` — chat router; `get_tab` (around line 671) is the target
- `orch/chat/opencode/client.py` — `get_session`, `get_messages`, `get_providers`
- `orch/chat/pi/pi_runtime.py` — `get_session`, `get_messages` (Pi runtime)
- `tests/integration/_fake_opencode.py` — fake OpenCode server used by integration tests
- `tests/integration/test_chat_tabs_api.py` — existing chat-tabs API integration tests

## Output Files

- `orch/chat/context_usage.py` — new pure helper module
- `dashboard/routers/chat.py` — modified (`get_tab` injects `context_pct`)
- `tests/unit/test_context_usage.py` — new unit tests for the helper
- `tests/integration/test_chat_tabs_api.py` — extended (or a sibling integration test file)
- `tests/integration/_fake_opencode.py` — extended to serve message `tokens` + provider `limit`
- `ai-dev/work/CR-00067/reports/CR-00067_S01_Backend_report.md` — report

## Context

The AI Assistant frontend (`chat.js`) reads `session.context_pct` from
`GET /api/chat/tabs/{id}`, but **no backend code ever produces that field**.
`get_tab` (`chat.py:671`) returns the raw runtime `session` object:
`OpencodeClient.get_session()` returns the OpenCode `GET /session/{sid}` body
verbatim, and `PiRuntime.get_session()` returns only `{"id", "pi_session_path"}`.
Neither carries a context-usage percentage. This step computes `context_pct` and
adds it to the `get_tab` response so the (separately implemented) frontend has a
real value to display.

## Task

This step follows TDD: **RED → GREEN → REFACTOR**. Write the failing test first,
run it, confirm it fails for the right reason, record the RED output in the
report, then implement.

### 1. New helper — `orch/chat/context_usage.py`

Create a pure module (no I/O, no DB, no HTTP) with a function that computes the
context-usage percentage. Suggested shape:

```python
def compute_context_pct(messages: list[dict], context_window: int | None) -> float | None:
    """Return context-window usage as a percentage in [0, 100], or None.

    Returns None when usage cannot be determined: no assistant message carries
    token usage, or context_window is missing / not positive.
    """
```

Rules:

- Scan `messages` for the **most recent** assistant message that carries token
  usage. OpenCode assistant messages expose a `tokens` object shaped roughly
  `{"input": int, "output": int, "reasoning": int, "cache": {"read": int, "write": int}}`.
  Treat **every** sub-field as optional — default each to `0`. Message role may
  appear as `message["role"]` or nested under `message["info"]["role"]`
  depending on the OpenCode payload shape — handle both defensively.
- `used_tokens = input + output + reasoning + cache.read + cache.write`.
- If no assistant message has a positive `used_tokens`, or `context_window` is
  `None` / `<= 0`, return `None`.
- Otherwise `pct = used_tokens / context_window * 100`, **clamped to `[0, 100]`**.
- Return a number (a `float`); the frontend rounds it for display. Do NOT round
  to `0` and return `0` for the "no data" case — return `None`.

Keep the arithmetic and all the missing-field defaulting in this pure module so
it is fully unit-testable without HTTP.

### 2. Model context-window lookup (cached)

The active model's context-window size comes from the OpenCode
`/config/providers` response: `providers[].models[<modelId>].limit.context`.
`OpencodeClient.get_providers()` already fetches that payload.

- Determine the active model for the tab. Prefer the `providerID` / `modelID`
  on the most recent assistant message; fall back to `tab.model` (a
  `"<providerId>/<modelId>"` string) when the message does not carry it.
- Add a helper that returns the `limit.context` integer for a given
  `"<providerId>/<modelId>"`, or `None` when unknown.
- **Do NOT add an uncached HTTP round-trip to every `get_tab` call** — `get_tab`
  is polled every 5 s by the frontend. Serve the providers payload from a
  short-TTL cache. Reuse the existing `_config_cache` / `_CONFIG_TTL` pattern in
  `chat.py` (or mirror it) rather than calling `get_providers()` unconditionally.

### 3. Wire into `get_tab` (`dashboard/routers/chat.py`)

After `session` and `messages` are fetched, compute `context_pct` and inject it
into the `session` dict before returning:

- Only inject when `session` is a dict and a numeric percentage was computed.
- When `context_pct` cannot be computed, **leave the field absent** — do not set
  it to `0` or `None`.
- The return shape stays `{"tab", "session", "messages"}`; `context_pct` lives
  *inside* `session` so the frontend's existing `data.session.context_pct`
  lookup keeps working unchanged.
- Apply this to the **OpenCode** path. For the **Pi** path, investigate whether
  `PiRuntime` session / messages expose token usage and a context limit. If they
  do, compute `context_pct` the same way; if they do not, leave `context_pct`
  absent for Pi tabs (the frontend label simply stays hidden — acceptable
  graceful degradation). Record what you found about Pi in the report.
- Any failure to fetch providers / compute usage must be swallowed — `get_tab`
  must never start returning an error because the percentage could not be
  computed.

### 4. Tests

- **Unit** (`tests/unit/test_context_usage.py`): cover token summing with
  missing sub-fields, the most-recent-assistant-message selection, percentage
  computation, `[0, 100]` clamping, and every `None` path (no messages, no
  assistant message, no token data, `context_window` `None` / `0` / negative).
  Assertions must be strong enough to fail if the production logic regresses.
- **Integration** (`tests/integration/`): extend `_fake_opencode.py` so it can
  serve assistant-message `tokens` and provider-model `limit.context`, then
  assert `GET /api/chat/tabs/{id}` returns a correct numeric
  `session.context_pct` when token data is present, and that the field is
  **absent** when it is not. Do NOT connect to the live DB; use testcontainers
  per `tests/CLAUDE.md`.

## Constraints

- Backend change only. Do NOT modify `composer.html`, `chat.css`, or `chat.js`
  — the frontend display is delivered by S02.
- Stay within the design's **Impacted Paths**: `orch/chat/context_usage.py`,
  `dashboard/routers/chat.py`, `tests/unit/**`, `tests/integration/**`.
- Keep `dashboard/routers/chat.py` thin — the computation logic belongs in
  `orch/chat/context_usage.py`, not inline in the router.
- `context_pct` is **additive and optional** — never make it a required field,
  never break the existing `{tab, session, messages}` contract.

## Quality Gates (run before reporting)

```bash
make lint
make format-check
uv run mypy orch/chat/context_usage.py dashboard/routers/chat.py
uv run pytest tests/unit/test_context_usage.py
uv run pytest tests/integration/test_chat_tabs_api.py
```

Run only the targeted test files above for verification — do NOT run
`make test-integration` / `make test-unit` at large in this step (the full
suites are owned by the S07 / S08 QV gates). All targeted commands must pass
with no new violations in changed files.

## Subagent Result Contract

```bash
uv run iw step-done CR-00067 --step S01 \
  --report ai-dev/work/CR-00067/reports/CR-00067_S01_Backend_report.md
```

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00067",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/chat/context_usage.py",
    "dashboard/routers/chat.py",
    "tests/unit/test_context_usage.py",
    "tests/integration/test_chat_tabs_api.py",
    "tests/integration/_fake_opencode.py"
  ],
  "tests_passed": true,
  "test_summary": "RED recorded; unit + integration tests green; lint/format/mypy clean",
  "blockers": [],
  "notes": "Pi runtime: <state whether context_pct could be computed for Pi tabs>"
}
```
