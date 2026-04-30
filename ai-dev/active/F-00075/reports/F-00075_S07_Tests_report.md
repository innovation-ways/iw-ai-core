# F-00075_S07_Tests Report

## What was done

Added comprehensive unit-test coverage for the MiniMax path in `orch/llm_usage.py` and the router-level pass-through. Also captured a live API response as a fixture.

## Files Changed

### `tests/fixtures/minimax_remains.json` (new)
Live MiniMax `/coding_plan/remains` response captured on 2026-04-30 21:02 UTC.
- `base_resp.status_code == 0`
- Contains `MiniMax-M*` row with `total=4500`, `usage_count=4232` remaining → **268 used**
- No API key or PII present

### `tests/unit/test_llm_usage.py` (replaced)
Complete test suite for the MiniMax path (38 tests total):

| Test class | Tests | Coverage |
|---|---|---|
| `TestLoadMinimaxKey` | 6 | env var wins, empty string treated as unset, auth.json fallback, missing, malformed, no minimax section |
| `TestFormatReset` | 7 | zero→None, negative→None, <1h→minutes, exactly 1h→"1h 0m", >1h→"Xh Ym" |
| `TestMinimaxUsageRemote` | 11 | real fixture happy-path, mid-window (33%), fully consumed (100%), missing row→LookupError, total=0→ValueError, non-zero status→RuntimeError, HTTPStatusError propagates, Bearer header, GroupId append, no GroupId, timeout ≤10s |
| `TestMinimaxUsage` | 7 | no key→{0,None}+warning, remote success, status_code error, HTTP error, ConnectTimeout, malformed JSON, missing M-row |
| `TestCacheTTL` | 2 | within-TTL→single HTTP call, data-seeded cache returns without HTTP |
| `TestGetLlmUsageShape` | 1 | catastrophic failure still returns `{block_pct, block_reset}` |
| `TestNoSqliteRegressions` | 4 | no sqlite3 import, no _OPENCODE_DB, no _FIVE_H_MS, no _MINIMAX_5H_LIMIT |

**Not included (by design):**
- Router smoke tests (`test_router_passes_minimax_reset_to_template`, `test_router_handles_failure_dict`) — per `tests/CLAUDE.md` "NEVER import `dashboard.routers.*` in a unit test unless a testcontainer `db_session` is in scope." Adding these would require a testcontainer-backed integration test, which is out of scope for pure unit tests. The router is a thin passthrough with no business logic.

## Pre-flight Quality Gates

- **format**: `uv run ruff format --check .` → all clean (503 files)
- **typecheck**: `uv run mypy orch/ dashboard/` → Success: no issues found
- **lint**: `uv run ruff check .` → All checks passed!

## Test Results

```
make test-unit
===== 2237 passed, 2 skipped, 5 xfailed, 1 xpassed, 48 warnings in 54.71s =====
```

Coverage: 51.98% (required: 46%) — all thresholds met.

## Notes

1. **Fixture value discrepancy**: The prompt referenced `usage_count=4234` in the conversation history. The live fixture captured on 2026-04-30 shows `4232`. Tests use the actual captured value (268 used → 6% block_pct).

2. **Cache TTL behaviour**: The `get_llm_usage()` cache logic checks `if _cache.get("ts") and (now - _cache["ts"]).total_seconds() < _CACHE_TTL`. The cache check only looks at `ts` — if `data` is missing, it raises `KeyError`. Test `test_second_call_hits_cache_when_data_seeded` seeds both `ts` and `data` to correctly test the cached-return path.

3. **`_load_minimax_key` patching complexity**: Patching `orch.llm_usage._load_minimax_key` via monkeypatch on a function that is called at module import time inside `_minimax_usage()` is unreliable (the function reference is captured at import). The `test_no_key_returns_zero_and_logs_warning` test instead monkeypatches the function object directly (`monkeypatch.setattr("orch.llm_usage._load_minimax_key", lambda: None)`).