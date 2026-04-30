# F-00075 S01 Backend Report

## Summary

Implemented the backend slice of F-00075: replaced the erroneous local SQLite computation in `orch/llm_usage.py` with a direct call to MiniMax's `/coding_plan/remains` API endpoint, and deleted the SQLite code path entirely.

## What Was Done

### 1. `orch/llm_usage.py` changes

- **Added `_load_minimax_key() -> str | None`**: resolves API key from `IW_MINIMAX_API_KEY` env var first, then falls back to `~/.local/share/opencode/auth.json` → `["minimax"]["key"]`. Returns `None` on any failure (never raises).

- **Added `_format_reset(remains_ms: int) -> str | None`**: formats milliseconds-to-reset as `"Xh Ym"` or `"Ym"`, mirroring the Claude path's format. Returns `None` for `remains_ms <= 0`.

- **Added `_minimax_usage_remote(api_key: str) -> dict[str, Any]`**: calls `GET https://api.minimax.io/v1/api/openplatform/coding_plan/remains` with `Authorization: Bearer {key}` and `Accept: application/json`. Honors optional `IW_MINIMAX_GROUP_ID` env var (appended as `?GroupId=`). Validates `base_resp.status_code == 0`, finds the `MiniMax-M*` row, computes `used = total - remaining` (API field is remaining, not used), computes `pct = min(100, round(used / total * 100))`, formats reset via `_format_reset()`. Returns `{"block_pct", "block_reset", "used", "total"}`.

- **Rewrote `_minimax_usage() -> dict[str, Any]`**: now an orchestrator that calls `_load_minimax_key()` then `_minimax_usage_remote()`. Never raises — all exceptions are caught and return `{"block_pct": 0, "block_reset": None}` with appropriate logging (`logger.warning` for missing key, `logger.exception` for runtime failures).

- **Updated outer `get_llm_usage()` wrapper**: the MiniMax `except` branch now returns `{"block_pct": 0, "block_reset": None}` (matching the new contract) instead of just `{"block_pct": 0}`.

- **Deleted SQLite code path**: removed `import sqlite3`, `_OPENCODE_DB`, `_FIVE_H_MS`, `_MINIMAX_5H_LIMIT`, and the entire old `_minimax_usage()` body. `Path` import retained because `_CLAUDE_JSONL_DIR` still uses `Path.home()`.

- **Updated module docstring**: accurately describes the new MiniMax behavior (live API call, auth resolution, GroupId escape hatch, failure behavior). Claude paragraphs untouched.

### 2. `.env.example` update

Added new MiniMax entries at the end of the file:
```
# --- Optional: MiniMax Coding Plan API key ---
# Resolved from IW_MINIMAX_API_KEY env var first; falls back to
# ~/.local/share/opencode/auth.json if unset.
# IW_MINIMAX_API_KEY=
# Optional GroupId for the /coding_plan/remains endpoint. Most accounts don't need this.
# IW_MINIMAX_GROUP_ID=
```

### 3. `tests/unit/test_llm_usage.py` (new file)

25 tests covering:
- `_load_minimax_key()`: env var wins, auth.json fallback, both missing → `None`, malformed JSON → `None`, missing minimax key → `None`
- `_format_reset()`: `< 1h` → `"Ym"`, `>= 1h` → `"Xh Ym"`, `0` → `None`
- `_minimax_usage_remote()`: happy path (0% used), mid-window (33%), fully consumed (100%), missing M* row → `LookupError`, total=0 → `ValueError`, status_code!=0 → `RuntimeError`, GroupId appended, no GroupId → no query string
- `_minimax_usage()`: missing key → warning + 0%, remote failure → exception + 0%
- Outer wrapper: catastrophic failure returns correct dict shape with both keys
- SQLite regression tests: verify `sqlite3`, `_OPENCODE_DB`, `_FIVE_H_MS`, `_MINIMAX_5H_LIMIT` are absent from module

## Files Changed

| File | Change |
|------|--------|
| `orch/llm_usage.py` | Rewrite MiniMax path + docstring update |
| `.env.example` | Added `IW_MINIMAX_API_KEY` and `IW_MINIMAX_GROUP_ID` |
| `tests/unit/test_llm_usage.py` | New test file (25 tests) |

## Pre-flight Results

| Check | Result |
|-------|--------|
| `make format` | ok (ruff format applied, no further drift) |
| `make typecheck` | ok (0 mypy errors) |
| `make lint` | ok (0 ruff errors) |
| `grep SQLite symbols` | 0 matches (AC6 satisfied) |
| `make test-unit` | 25 passed in `test_llm_usage.py`; 2 pre-existing failures in `test_safe_migrate.py` (unrelated to this change) |

## Pre-existing Test Failures (Not Related to This Change)

`test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context` and `test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context` fail — these are pre-existing and unrelated to F-00075. `test_safe_migrate.py` was not modified by this step.

## Notes

- The `Path` import was retained because `_CLAUDE_JSONL_DIR` (used by `_sum_jsonl_tokens()`) still uses `Path.home()`.
- `httpx` was already a declared dependency (`pyproject.toml:55`).
- All 25 tests in `test_llm_usage.py` pass with zero failures.
- SQLite regression tests confirm the deprecated symbols are fully removed.
