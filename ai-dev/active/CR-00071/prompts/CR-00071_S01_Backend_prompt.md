# CR-00071_S01_Backend_prompt

**Work Item**: CR-00071 — Pi Runtime Context-Usage Percentage Support
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step writes no migrations. The context-window column already exists
(`agent_runtime_options.context_window_tokens`, CR-00066). Full policy:
docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00071 --json`
- `ai-dev/active/CR-00071/CR-00071_CR_Design.md` — Design document
- `orch/CLAUDE.md` · `dashboard/CLAUDE.md` · `tests/CLAUDE.md` — package + test conventions
- `skills/iw-ai-core-testing/SKILL.md` — **read before writing any test**
- `dashboard/routers/chat.py` — chat router; `get_tab` is the target. Study the
  **OpenCode** branch's `context_pct` injection block (the `contextlib.suppress`
  block after `session`/`messages` are fetched) and the **Pi** branch (the
  `if tab.runtime == "pi":` block that returns early without `context_pct`).
- `orch/chat/context_usage.py` — existing pure helpers: `compute_context_pct`,
  `lookup_context_window`, `resolve_model_from_tab`
- `orch/chat/pi/pi_runtime.py` — `PiRuntime.get_session`, `PiRuntime.get_messages`
- `orch/chat/pi/pi_rpc_client.py` · `orch/chat/pi/event_normalizer.py` ·
  `orch/chat/pi/pi_jsonl_reader.py` — Pi RPC/message machinery, for the token-shape investigation
- `orch/db/models.py` — `AgentRuntimeOption` (the Pi model catalogue; the
  `context_window_tokens` column is the Pi context-window source)
- `tests/dashboard/test_chat_router_pi.py` — existing Pi-path router tests
- `tests/integration/test_chat_tabs_api.py` — existing chat-tabs API integration tests (OpenCode `context_pct` cases)

## Output Files

- `dashboard/routers/chat.py` — modified (`get_tab` Pi branch injects `context_pct`)
- `orch/chat/context_usage.py` — modified **only if** a Pi token-shape normalizer is needed (see Task §1)
- `tests/unit/test_context_usage.py` — extended **only if** a normalizer was added
- Integration test for the Pi `context_pct` path — extend `tests/dashboard/test_chat_router_pi.py`
  or add a sibling test file under `tests/integration/`
- `ai-dev/work/CR-00071/reports/CR-00071_S01_Backend_report.md` — report

## Context

CR-00067 added a context-usage percentage to the AI Assistant footer. The
frontend (`chat.js`) reads `session.context_pct` from `GET /api/chat/tabs/{id}`,
but the backend only produces that field for **OpenCode** tabs. In `get_tab`,
the Pi branch (`if tab.runtime == "pi":`) fetches `session`/`messages` and
`return`s `{tab, session, messages}` immediately — it never reaches the
`context_pct` injection block, which lives only in the OpenCode branch below it.

Commit `365413e1` made Pi the AI Assistant default runtime, so every new chat
tab is a Pi tab and the indicator is now dark for effectively all chats. This
step extends the Pi branch to compute and inject `context_pct`.

Two facts make this low-risk and small:

- `compute_context_pct(messages, context_window)` in `orch/chat/context_usage.py`
  is **already runtime-agnostic** — give it a message list and an integer
  context window and it returns the percentage, or `None` when usage cannot be
  determined.
- The Pi context-window source already exists: `AgentRuntimeOption.context_window_tokens`
  (nullable `Integer`, added by CR-00066). Pi tab models are stored as
  `"pi/<model>"`, i.e. `cli_tool="pi"`, `model="<model>"`.

## Task

This step follows TDD: **RED → GREEN → REFACTOR**. Write the failing test
first, run it, confirm it fails for the right reason, record the RED output in
the report, then implement.

### 1. Investigate the Pi per-message token shape (do this first)

`compute_context_pct` reads token usage from each message's `tokens` object,
shaped (OpenCode) as `{"input", "output", "reasoning", "cache": {"read", "write"}}`,
with the role at `message["role"]` or `message["info"]["role"]`.

`PiRuntime.get_messages()` returns whatever the `pi` subprocess sends for a
`{"type": "get_messages"}` RPC. Determine the actual Pi message shape:

- Inspect `orch/chat/pi/` (`pi_rpc_client.py`, `event_normalizer.py`,
  `pi_jsonl_reader.py`) for any message/token normalisation.
- If a `pi` binary is available on `PATH`, drive a short session and dump a
  real `get_messages` payload. If no `pi` binary is available, say so in the
  report and proceed on the documented shape you can infer from the Pi source.

Three outcomes — **all are acceptable and none block the CR**:

  1. **Pi token keys already match the OpenCode shape** → no normalizer needed;
     pass Pi `messages` straight to `compute_context_pct`.
  2. **Pi token keys differ** (different field names / nesting) → add a small
     **pure** normalizer to `orch/chat/context_usage.py` that maps a Pi message
     list into the shape `compute_context_pct` consumes. Keep it pure — no DB,
     no I/O.
  3. **Pi exposes no per-message token usage at all** → still wire the branch
     (it is harmless: `compute_context_pct` returns `None`, the indicator stays
     hidden = current behaviour). Record the finding clearly in the report so a
     follow-up can revisit if Pi later exposes tokens.

Record which outcome you found and why, in the report.

### 2. Pi context-window lookup

Add the lookup that resolves a Pi tab's context window from the DB:

- Resolve the Pi model from `tab.model`. A Pi tab's `model` is `"pi/<model>"` —
  split on the first `/` into `cli_tool` and `model`. You may reuse
  `context_usage.resolve_model_from_tab` if it yields a usable `(provider, model)`
  pair from `tab.model`; otherwise split inline in the router.
- Query `AgentRuntimeOption` for the row matching `(cli_tool="pi", model=<model>)`
  and read `context_window_tokens`. Return `None` when no row matches or
  `context_window_tokens` is `NULL`.
- This is a DB query — it MUST live in `dashboard/routers/chat.py` (the router
  already holds a `Session`), **not** in `orch/chat/context_usage.py`, which is
  documented as pure (no I/O, no DB). Any helper you add to `context_usage.py`
  must stay pure.
- **No new cache needed.** Unlike the OpenCode `/config/providers` HTTP lookup
  (cached in `_providers_cache`), this is a single indexed read on a tiny
  catalogue table — acceptable on every `get_tab` poll. Do NOT add a cache layer.

### 3. Wire into the `get_tab` Pi branch (`dashboard/routers/chat.py`)

In the Pi branch of `get_tab`, after `session` and `messages` are fetched and
before the `return`, compute `context_pct` and inject it into the `session`
dict — mirroring the OpenCode branch:

- Wrap the whole computation in `contextlib.suppress(Exception)` (same as the
  OpenCode branch) so any failure is non-fatal — `get_tab` must never start
  returning an error because the percentage could not be computed.
- Only inject when `session` is a dict and a numeric percentage was computed.
- When `context_pct` cannot be computed (no token data, no `context_window_tokens`
  row, anything else), **leave the field absent** — never `0`, never `None`.
- The return shape stays `{"tab", "session", "messages"}`; `context_pct` lives
  *inside* `session`.
- **Do NOT touch the OpenCode branch.** Its behaviour must stay byte-for-byte
  unchanged (AC4).

### 4. Tests

- **Unit** (`tests/unit/test_context_usage.py`): only if Task §1 produced a
  normalizer — cover it directly: Pi-shaped messages with/without tokens,
  partial token fields, malformed input → safe defaults. Strong assertions that
  fail on a logic regression. `compute_context_pct` itself is already covered by
  CR-00067 — do not duplicate that coverage.
- **Integration** (`tests/dashboard/test_chat_router_pi.py` or a sibling
  `tests/integration/` file): assert `GET /api/chat/tabs/{tab_id}` on a **Pi**
  tab —
  - **AC1**: injects a correct numeric `session.context_pct` when `PiRuntime.get_messages`
    is mocked to return token-bearing messages (in the shape you found in §1)
    and an `agent_runtime_options` row with a positive `context_window_tokens`
    exists for the tab's model.
  - **AC2**: omits `context_pct` when Pi messages carry no token usage.
  - **AC3**: omits `context_pct` when the model's `agent_runtime_options` row
    has `context_window_tokens = NULL`.
  - The existing `test_chat_router_pi.py` cases mock `get_messages` returning
    `[]` — keep them; that already exercises AC2's empty case.
  - Seed `agent_runtime_options` rows in the testcontainer. Do NOT connect to
    the live DB; use testcontainers per `tests/CLAUDE.md`.
- Confirm the existing OpenCode `context_pct` integration tests in
  `tests/integration/test_chat_tabs_api.py` still pass unchanged (AC4).

## Constraints

- Backend change only. Do NOT modify `composer.html`, `chat.css`, or `chat.js`
  — the frontend already consumes `session.context_pct` generically (CR-00067)
  and needs no change.
- Stay within the design's **Impacted Paths**: `dashboard/routers/chat.py`,
  `orch/chat/context_usage.py`, `tests/unit/**`, `tests/integration/**`,
  `tests/dashboard/**`.
- `orch/chat/context_usage.py` must stay **pure** — no DB, no HTTP, no I/O.
- Keep `dashboard/routers/chat.py` thin — arithmetic/normalisation belongs in
  `context_usage.py`; only the DB query and wiring belong in the router.
- `context_pct` is **additive and optional** — never a required field, never
  break the `{tab, session, messages}` contract.

## Quality Gates (run before reporting)

```bash
make lint
make format-check
uv run mypy dashboard/routers/chat.py orch/chat/context_usage.py
uv run pytest tests/dashboard/test_chat_router_pi.py
uv run pytest tests/unit/test_context_usage.py
uv run pytest tests/integration/test_chat_tabs_api.py
```

Run only the targeted test files above for verification — do NOT run
`make test-integration` / `make test-unit` at large in this step (the full
suites are owned by the S06 / S07 QV gates). All targeted commands must pass
with no new violations in changed files.

## Subagent Result Contract

```bash
uv run iw step-done CR-00071 --step S01 \
  --report ai-dev/work/CR-00071/reports/CR-00071_S01_Backend_report.md
```

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00071",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/chat.py",
    "tests/dashboard/test_chat_router_pi.py"
  ],
  "tests_passed": true,
  "test_summary": "RED recorded; Pi context_pct unit + integration tests green; lint/format/mypy clean",
  "tdd_red_evidence": "<the RED run command + a plausible AssertionError snippet>",
  "blockers": [],
  "notes": "Pi token shape investigation: <outcome 1/2/3 and what was found>"
}
```
