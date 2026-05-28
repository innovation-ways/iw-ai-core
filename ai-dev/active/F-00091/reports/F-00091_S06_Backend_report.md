# F-00091 S06 Backend Report

## What was done
- Added typed context-usage resolution in `orch/chat/context_usage.py`:
  - `ContextUsage` dataclass
  - `resolve_context_usage_opencode(...)`
  - `resolve_context_usage_pi(...)`
  - invariant assertion helper enforcing: `status == "known"` iff `context_pct`, `used_tokens`, `window_tokens` are all present and valid.
- Updated `GET /api/chat/tabs/{tab_id}` in `dashboard/routers/chat.py` to always set:
  - `context_pct`
  - `context_pct_status`
  - `used_tokens`
  - `window_tokens`
  - `context_pct_reason`
  with fallback to `unknown_runtime` + `unexpected error` if resolver throws.
- Kept payload additive/backward compatible (`context_pct` preserved).

## Files changed
- `orch/chat/context_usage.py`
- `dashboard/routers/chat.py`
- `tests/unit/test_context_usage_status.py`
- `tests/dashboard/test_chat_tabs_status_payload.py`

## Test results
- `uv run pytest tests/unit/test_context_usage_status.py tests/dashboard/test_chat_tabs_status_payload.py -v`
  - **9 passed, 0 failed**

## Quality gates
- `make format` initially failed (required formatting); fixed by running ruff format on new tests.
- `make typecheck` passed.
- `make lint` initially failed on S101 for invariant assert; fixed with `# noqa: S101` on the required invariant assert line.
- Final status: all gates passing.

## Issues / observations
- Pi unknown-runtime branch returns 503 before session payload shaping in `get_tab`; this step still covers unknown-runtime status in helper unit tests as requested.
