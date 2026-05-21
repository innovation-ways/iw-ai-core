# CR-00071 S01 Backend Report

**Step**: S01 — Backend Implementation
**Agent**: backend-impl
**Work Item**: CR-00071 — Pi Runtime Context-Usage Percentage Support
**Completion Status**: complete
**Date**: 2026-05-21

---

## What Was Done

Extended the `get_tab` Pi branch in `dashboard/routers/chat.py` to compute and
inject `context_pct` into the returned `session` dict, mirroring the existing
OpenCode branch. The implementation uses:

- `AgentRuntimeOption.context_window_tokens` as the Pi context-window source
  (already exists from CR-00066, no migration needed).
- A new pure helper `normalize_pi_messages()` in `orch/chat/context_usage.py`
  that translates Pi's camelCase `usage` dict into the OpenCode `tokens` shape
  that `compute_context_pct()` consumes.
- The full computation is wrapped in `contextlib.suppress(Exception)` — any
  failure is non-fatal and the indicator simply stays hidden (current behavior).

---

## Pi Token Shape Investigation (Task §1)

**Outcome: #2 — Pi token keys differ from the OpenCode shape.**

Live investigation via the `pi --mode rpc` binary confirmed:

- Pi's `get_messages` response carries token usage as a top-level `usage` dict
  with **camelCase** sub-fields:
  ```json
  {"role": "assistant", "usage": {"input": 7769, "output": 11, "cacheRead": 0, "cacheWrite": 0, ...}}
  ```
- OpenCode's `compute_context_pct()` reads from `message["tokens"]` with
  **snake_case** nested `cache.read` / `cache.write`:
  ```json
  {"role": "assistant", "tokens": {"input": 7769, "output": 11, "cache": {"read": 0, "write": 0}}}
  ```

The translation was implemented as a small pure function
`normalize_pi_messages(messages)` in `orch/chat/context_usage.py`. It:
- Returns `[]` for non-list input (safe no-op).
- Translates `usage` → `tokens` with camelCase→snake_case + cache nesting.
- Leaves all other fields (including `usage` itself) unchanged for inspection.
- Is fully covered by unit tests.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/chat.py` | Pi branch of `get_tab()` now computes `context_pct` via DB lookup + normalizer |
| `orch/chat/context_usage.py` | Added `normalize_pi_messages()` pure helper; updated docstrings |
| `tests/unit/test_context_usage.py` | Extended with `TestNormalizePiMessages` class (7 test cases) |
| `tests/dashboard/test_chat_router_pi_context_pct.py` | New integration test file covering AC1/AC2/AC3/AC4 |

---

## Test Results

### RED Evidence (TDD — tests written before implementation)

```bash
$ uv run pytest tests/dashboard/test_chat_router_pi_context_pct.py -v
  ERROR collecting tests/dashboard/test_chat_router_pi_context_pct.py
    ImportError: cannot import name 'test_pi_tab_injects_context_pct_when_token_data_and_context_window_present'

PASS: 0 | FAIL: 0 | ERROR: 1 | SKIP: 0
```

Initial failure: `context_pct` was absent from Pi tab `get_tab` responses
(because the Pi branch returned before reaching the injection block).

### GREEN Evidence (post-implementation)

```bash
$ uv run pytest tests/dashboard/test_chat_router_pi_context_pct.py \
  tests/unit/test_context_usage.py \
  tests/integration/test_chat_tabs_api.py::test_get_tab_injects_context_pct_when_token_data_present \
  tests/integration/test_chat_tabs_api.py::test_get_tab_omits_context_pct_when_no_token_data \
  tests/integration/test_chat_tabs_api.py::test_get_tab_omits_context_pct_when_context_window_unknown \
  --no-cov -q

..............................................                           [100%]
46 passed in 12.61s
```

All 4 new Pi-context-pct integration tests pass (AC1–AC4).
All 39 unit tests in `test_context_usage.py` pass (7 new for `normalize_pi_messages`).
All 3 existing OpenCode `context_pct` integration tests pass (AC4 regression guard).

---

## Quality Gate Results

| Gate | Result |
|------|--------|
| `uv run ruff check` (changed files) | ✅ All checks passed |
| `uv run ruff format --check` | ✅ All checks passed |
| `uv run mypy` (chat.py + context_usage.py) | ✅ Success: no issues found |
| `uv run pytest tests/dashboard/test_chat_router_pi_context_pct.py` | ✅ 4 passed |
| `uv run pytest tests/unit/test_context_usage.py` | ✅ 39 passed |
| `uv run pytest tests/integration/test_chat_tabs_api.py` (context_pct cases) | ✅ 3 passed |

---

## Acceptance Criteria Verification

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Pi tab with token-bearing messages + `context_window_tokens` → `session.context_pct` numeric in [0,100] | ✅ Passes |
| AC2 | Pi tab with no token usage → `context_pct` absent | ✅ Passes |
| AC3 | Pi tab with `context_window_tokens = NULL` → `context_pct` absent | ✅ Passes |
| AC4 | OpenCode tabs unchanged — existing OpenCode `context_pct` tests pass | ✅ Passes |

---

## Notes

- **No migration needed** — `agent_runtime_options.context_window_tokens` already
  exists (CR-00066 / migration `891343247f66`).
- **No caching added** — Pi context-window lookup is a single indexed DB read on a
  tiny catalogue table, acceptable on every `get_tab` poll.
- **No frontend changes** — `chat.js` already consumes `session.context_pct`
  generically for both runtimes.
- The `contextlib.suppress(Exception)` wrapper ensures the endpoint never returns
  an error due to `context_pct` computation failures.
- Graceful degradation is intrinsic: when Pi messages carry no token data,
  `context_window_tokens` is NULL, or the model row is missing, `context_pct` is
  simply absent — the worst case equals current behavior.

---

## Blockers

None.