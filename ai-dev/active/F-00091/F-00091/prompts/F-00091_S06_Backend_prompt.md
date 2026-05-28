# F-00091_S06_Backend_prompt

**Work Item**: F-00091 -- AI Assistant — Decouple from page URL, persist per-project tab, and surface an always-visible context-usage progress bar
**Step**: S06
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step adds no migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00091 --json`
- `ai-dev/active/F-00091/F-00091_Feature_Design.md` — Design (read Scope → S06, AC3, AC4, Invariant 7, and the API Changes section)
- `dashboard/routers/chat.py:734-823` — `get_tab` and the current context_pct injection logic
- `orch/chat/context_usage.py` — Existing helpers (`normalize_pi_messages`, `compute_context_pct`, `lookup_context_window`, `resolve_model_from_tab`)
- `orch/db/models.py:56` — `AgentRuntimeOption` model (especially `context_window_tokens` and `max_output_tokens`)

## Output Files

- `ai-dev/work/F-00091/reports/F-00091_S06_Backend_report.md`

## Context

Today `GET /api/chat/tabs/{tab_id}` either includes a `session.context_pct` float OR silently omits the key when its lookup chain breaks. S07 will render a progress bar that needs THREE pieces of information from the server:

1. The numeric percentage (already present as `context_pct`).
2. The raw token counts so the tooltip can show "120k / 200k tokens".
3. An explicit status so the bar can render the unknown branch when the percent is unavailable.

This step extends the payload additively. No client breaks.

Read **Scope → S06**, **AC3**, **AC4**, **Invariant 7**, and the **API Changes** section before touching code.

## Requirements

### 1. New helper in `orch/chat/context_usage.py`

Add a function `resolve_context_usage(...)` that returns a typed result describing the four possible states:

```python
@dataclass(frozen=True)
class ContextUsage:
    status: Literal["known", "unknown_window", "unknown_runtime"]
    pct: float | None        # only set when status == "known"
    used_tokens: int | None  # only set when status == "known"
    window_tokens: int | None  # only set when status == "known"
    reason: str | None       # human-readable, e.g., "Context window not configured for pi/<model>"
```

The function takes the inputs `get_tab` already has at hand:

- For OpenCode: `(client_healthy: bool, providers: dict, tab_model: str | None, messages: list[Any])`.
- For Pi: `(pi_healthy: bool, agent_runtime_option: AgentRuntimeOption | None, tab_model: str | None, messages: list[Any])`.

If signatures get unwieldy, split into two functions (`resolve_context_usage_opencode`, `resolve_context_usage_pi`) returning the same `ContextUsage` shape.

Resolution rules:

- `client_healthy=False` (or Pi `pi_healthy=False`) → `status="unknown_runtime"`, `reason="<Runtime> runtime unavailable"`.
- Runtime healthy but model cannot be resolved against providers, OR `AgentRuntimeOption.context_window_tokens` is NULL → `status="unknown_window"`, `reason="Context window unknown for <runtime>/<model>"` (or similar; the design AC4 quotes a longer Pi-specific message — use that wording for Pi, a parallel one for OpenCode).
- Otherwise → `status="known"`, populate `pct`/`used_tokens`/`window_tokens`. `used_tokens = round(window_tokens * pct / 100)` is acceptable IF the messages list does not provide a direct token count — but prefer reading the token count straight from `messages[-1].tokens.input + messages[-1].tokens.output + messages[-1].tokens.cache_read + messages[-1].tokens.cache_write` if the existing `compute_context_pct` already does this. Audit `compute_context_pct` first; reuse its arithmetic, don't duplicate it.

### 2. Wire the new helper into `get_tab`

In `dashboard/routers/chat.py:734-823`:

- Replace both the OpenCode and Pi branches' `with contextlib.suppress(Exception): … session["context_pct"] = pct` blocks with calls to `resolve_context_usage(...)`.
- ALWAYS set `session["context_pct_status"]`, `session["used_tokens"]`, `session["window_tokens"]`, `session["context_pct_reason"]` even when status is unknown. Use `None` for `pct`, `used_tokens`, `window_tokens` in the unknown branches.
- KEEP the existing `session["context_pct"]` field (still a float in the known branch, `None` in the unknown branches) for backwards compatibility with any unmigrated client.
- The `contextlib.suppress(Exception)` defensive wrapper at the outer level should remain — any unexpected exception in the resolver falls through to `status="unknown_runtime"` with reason `"unexpected error"`. Do NOT let an exception in the resolver break the entire `/api/chat/tabs/{tab_id}` response.

### 3. Per Invariant 7

`context_pct_status == "known"` IFF `used_tokens`, `window_tokens` are non-null ints AND `context_pct` is a finite float. Encode that invariant as an explicit assertion at the end of `resolve_context_usage` (Python `assert`), guarded so it does not run in production-stripped mode. A consistency violation here is a bug, not a soft failure.

### 4. TDD

Add `tests/unit/test_context_usage_status.py`:

- One test per status branch: `known`, `unknown_window`, `unknown_runtime` — for BOTH OpenCode and Pi paths. Six tests minimum.
- One test asserting the additive shape (the four new keys are present in every branch).
- One test asserting `context_pct_status == "known"` exactly matches the (`pct`, `used_tokens`, `window_tokens` all non-null) condition.
- Verify the helper does NOT touch the DB directly — feed it the `AgentRuntimeOption` instance the caller already has.

Add a dashboard test `tests/dashboard/test_chat_tabs_status_payload.py` to verify the payload shape end-to-end via `TestClient` for at least the `known` and `unknown_window` cases (Pi path). The `unknown_runtime` case needs a stub or monkey-patched runtime health — use the existing fixture pattern.

Capture RED → GREEN. Record `tdd_red_evidence` from the unit test failures.

### 5. Do NOT touch

- The `chat_tabs` DB schema.
- The OpenCode or Pi client modules — only the consumer-side logic in `dashboard/routers/chat.py` and helpers in `orch/chat/context_usage.py`.
- The frontend. S07 owns the rendering changes.

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `dashboard/CLAUDE.md`. Specifically:

- Routers are thin — business logic stays in `orch/chat/`.
- SQLAlchemy 2.0 sync.
- Never connect tests to live DB (5433) — use testcontainers for the integration coverage S08 will add. Unit tests for this step should rely on plain object instantiation, no DB.

## TDD Requirement

Standard RED → GREEN → REFACTOR. Record RED in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Run only the test files you wrote:

```bash
uv run pytest tests/unit/test_context_usage_status.py tests/dashboard/test_chat_tabs_status_payload.py -v
```

Do NOT run the wider suite.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "backend-impl",
  "work_item": "F-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/chat/context_usage.py",
    "dashboard/routers/chat.py",
    "tests/unit/test_context_usage_status.py",
    "tests/dashboard/test_chat_tabs_status_payload.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_context_usage_status.py::test_unknown_window_pi — AssertionError: result.status == 'unknown_window', got KeyError",
  "blockers": [],
  "notes": ""
}
```
