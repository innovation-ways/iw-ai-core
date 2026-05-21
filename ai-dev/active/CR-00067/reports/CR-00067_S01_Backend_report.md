# CR-00067 S01 Backend Report

## What Was Done

Implemented the backend half of the Context Usage Percentage Indicator (CR-00067 S01).

### New Files

- **`orch/chat/context_usage.py`** — Pure helper module with three functions:
  - `compute_context_pct(messages, context_window)` — scans messages for the most-recent assistant message carrying token usage, sums `input + output + reasoning + cache.read + cache.write`, computes percentage clamped to `[0, 100]`, returns `None` when not computable.
  - `lookup_context_window(providers_raw, provider_id, model_id)` — looks up `limit.context` from the OpenCode `/config/providers` payload.
  - `resolve_model_from_tab(tab_model, messages)` — resolves `(provider_id, model_id)` from the most-recent assistant message's `info` fields, falling back to `tab.model`.
  - All fields default to 0 when absent; role resolved from `message["role"]` or `message["info"]["role"]` (OpenCode payload variant).

### Modified Files

- **`dashboard/routers/chat.py`** — Added `_PROVIDERS_TTL`, `_providers_cache`, `_get_providers_cached()` (30 s TTL cache for `/config/providers`), and injected `context_pct` computation into `get_tab` (lines 764–775). The injection is wrapped in `contextlib.suppress(Exception)` so any failure to compute never turns into an HTTP error.

- **`tests/integration/_fake_opencode.py`** — Extended `FakeOpencodeControl` with:
  - `_provider_model_limits: dict[tuple[str, str], int]` — per-(provider, model) context-window storage.
  - `set_messages(sid, messages)` — seed a session's message history.
  - `set_provider_model_limit(provider_id, model_id, context_limit)` — set `limit.context` for a provider+model.
  - `build_providers_response()` — builds the providers payload honouring stored limits.
  - Updated `get_config_providers` route to use `build_providers_response()`.

- **`tests/integration/test_chat_tabs_api.py`** — Added three integration tests:
  - `test_get_tab_injects_context_pct_when_token_data_present` — asserts `session.context_pct` is a float (≈14.7 for 14700 used / 100000 window).
  - `test_get_tab_omits_context_pct_when_no_token_data` — asserts `context_pct` absent when assistant messages carry no token usage.
  - `test_get_tab_omits_context_pct_when_context_window_unknown` — asserts `context_pct` absent when model has no `limit.context`.
  - Also added `chat_mod._providers_cache.clear()` to `_clear_chat_caches` autouse fixture.

- **`tests/unit/test_context_usage.py`** — Fixed import order (moved `import inspect` and `from orch.chat.context_usage import` to top of file) and removed commented-out arithmetic lines that failed `ERA001` lint.

### Pi Runtime Investigation

`PiRuntime.get_session()` returns only `{"id": session_id, "pi_session_path": ...}` with no token data. `PiRuntime.get_messages()` calls the Pi subprocess RPC and returns raw message dicts — token exposure is unknown and unverified without a live Pi binary. `context_pct` is therefore **omitted for Pi tabs** (graceful degradation — the frontend label stays hidden). A follow-up CR could investigate Pi message token exposure if needed.

## Files Changed

| File | Change |
|------|--------|
| `orch/chat/context_usage.py` | New pure helper module |
| `dashboard/routers/chat.py` | `_providers_cache`, `_get_providers_cached`, `get_tab` injection |
| `tests/integration/_fake_opencode.py` | `set_messages`, `set_provider_model_limit`, `build_providers_response` |
| `tests/integration/test_chat_tabs_api.py` | 3 new integration tests + cache clear fix |
| `tests/unit/test_context_usage.py` | Import order fix, ERA001 cleanup |

## Test Results

```
tests/unit/test_context_usage.py         — 32 passed
tests/integration/test_chat_tabs_api.py  — 16 passed (13 pre-existing + 3 new)
```

## Quality Gates

| Check | Result |
|-------|--------|
| `make lint` | PASSED |
| `make format-check` | PASSED (3 files already formatted) |
| `uv run mypy orch/chat/context_usage.py dashboard/routers/chat.py` | PASSED (no issues) |
| `uv run pytest tests/unit/test_context_usage.py` | 32 passed |
| `uv run pytest tests/integration/test_chat_tabs_api.py` | 16 passed |

## Notes

- The `_providers_cache` design mirrors the existing `_config_cache` pattern — both use a `{"data": ..., "at": ...}` slot with TTL.
- `context_pct` is injected only into the OpenCode path (not Pi). This is intentional graceful degradation.
- RED evidence was originally recorded in `tests/unit/test_context_usage.py` at the top of the file — the module did not exist, causing `ImportError: cannot import name 'compute_context_pct'`. All 32 tests are now GREEN.