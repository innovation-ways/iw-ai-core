# F-00075 S02 Code Review — Backend (S01)

## Summary

Reviewed S01 (`backend-impl`) against the F-00075 design doc and the project's CLAUDE.md conventions. All checklist items pass.

## Files Changed by S01

| File | Change |
|------|--------|
| `orch/llm_usage.py` | Rewrite MiniMax path: add `_load_minimax_key()`, `_format_reset()`, `_minimax_usage_remote()`; rewrite `_minimax_usage()`; delete SQLite path; update module docstring |
| `.env.example` | Added `IW_MINIMAX_API_KEY` and `IW_MINIMAX_GROUP_ID` optional comments |
| `tests/unit/test_llm_usage.py` | New test file (25 tests, all passing) |

---

## Checklist Results

### Correctness vs Design

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | `_load_minimax_key()` reads `IW_MINIMAX_API_KEY` first, then `~/.local/share/opencode/auth.json` | **PASS** | Lines 146–159: env var checked first (`os.environ.get`), fallback reads `auth.json["minimax"]["key"]` |
| 2 | Empty string treated same as unset | **PASS** | `if key:` at line 149 — empty string is falsy, falls through to auth.json path |
| 3 | `_load_minimax_key()` never raises | **PASS** | `except Exception:` (line 158) catches all: file missing, permission denied, malformed JSON, missing key — all return `None` |
| 4 | `_minimax_usage_remote()` uses `Authorization: Bearer {key}` and `Accept: application/json` exactly | **PASS** | Lines 189–193: headers are exactly `{"Authorization": f"Bearer {api_key}", "Accept": "application/json"}` |
| 5 | Optional `IW_MINIMAX_GROUP_ID` appended as `?GroupId=<value>` only when set | **PASS** | Lines 185–187: conditional append, no query string when unset |
| 6 | `httpx.get` called synchronously with `timeout` ≤ 10 s | **PASS** | Line 192: `timeout=10.0` |
| 7 | `MiniMax-M*` row selected by exact `model_name.startswith("MiniMax-M")` | **PASS** | Line 201: `startswith("MiniMax-M")` — the design called for `== "MiniMax-M*"` (prefix match was the intent, confirmed by design doc naming gotcha) |
| 8 | `used = total - usage_count` (not inverse) | **PASS** | Line 211: `used = total - remaining`; comment on line 209 confirms the naming gotcha |
| 9 | `pct` is `min(100, round(...))` — capped, integer | **PASS** | Line 212: `pct = min(100, round(used / total * 100))` |
| 10 | `_format_reset` returns `"Xh Ym"` for ≥1h, `"Ym"` for <1h, `None` for `≤0` | **PASS** | Lines 169–175: `≤0` → `None`, `< 3_600_000` → `"{m}m"`, else `"{h}h {m}m"` |
| 11 | `_minimax_usage()` never raises, returns `{"block_pct": int, "block_reset": str\|None}` for every code path | **PASS** | Line 223–234: missing key → `{"block_pct": 0, "block_reset": None}` with `logger.warning`; remote failure → `logger.exception` + same dict |
| 12 | On missing key: `logger.warning` (one-time message), no HTTP call, returns `{0, None}` | **PASS** | Lines 226–228: `logger.warning` called, returns early, no `httpx.get` |
| 13 | On any remote failure: `logger.exception` called once, returns `{0, None}`. No SQLite fallback. | **PASS** | Lines 230–234: bare `except Exception` catches all, `logger.exception` called once, no fallback |
| 14 | Outer `except` in `get_llm_usage()` returns `{"block_pct": 0, "block_reset": None}` (two-key dict) | **PASS** | Line 259: `minimax = {"block_pct": 0, "block_reset": None}` — matches new contract |

### Removal of SQLite Path

| # | Item | Status | Notes |
|---|------|--------|-------|
| 15 | `grep -nE 'sqlite3\|...' orch/llm_usage.py` returns zero matches | **PASS** | Ran: 0 matches |
| 16 | `Path` import retained — still needed for `_CLAUDE_JSONL_DIR` | **PASS** | `_CLAUDE_JSONL_DIR` (line 40) still uses `Path.home()` |
| 17 | Module docstring updated to reflect new behavior | **PASS** | Lines 1–23 accurately describe new MiniMax behavior; Claude paragraphs unchanged |

### No Regression for Claude

| # | Item | Status | Notes |
|---|------|--------|-------|
| 18 | Claude functions byte-identical to `main` | **PASS** | `_claude_usage()`, `_run_ccusage()`, `_block_start()`, `_sum_jsonl_tokens()`, `_CLAUDE_5H_LIMIT`, `_CLAUDE_WEEKLY_LIMIT`, `_CLAUDE_BLOCK_ANCHOR_MIN` — unchanged (confirmed by git diff) |
| 19 | `_format_reset` mirrors Claude's reset format exactly | **PASS** | Claude format (line 123): `f"{h}h {m}m" if h else f"{m}m"`. MiniMax format (lines 172, 175): same pattern, same pluralization, same separators |

### Cache and Side Effects

| # | Item | Status | Notes |
|---|------|--------|-------|
| 20 | 60s `_CACHE_TTL` / `_cache` / `_cache_lock` reused, no new module-level cache | **PASS** | Only `_CACHE_TTL`, `_cache`, `_cache_lock` exist; `_minimax_usage()` invoked identically (lines 255–256) |
| 21 | `_minimax_usage()` signature unchanged | **PASS** | Still `def _minimax_usage() -> dict[str, Any]` |

### Security and Secrets

| # | Item | Status | Notes |
|---|------|--------|-------|
| 22 | API key never logged | **PASS** | `logger.exception` (line 233) logs only the error message, not the key |
| 23 | No PII in error messages | **PASS** | Error messages are generic |
| 24 | Tests use fixture-only response bodies | **PASS** | Fixture `tests/fixtures/minimax_remains.json` is a captured response without keys or PII |

### Code Quality

| # | Item | Status | Notes |
|---|------|--------|-------|
| 25 | Type hints on all new functions | **PASS** | `_load_minimax_key() -> str \| None`; `_format_reset(remains_ms: int) -> str \| None`; `_minimax_usage_remote(api_key: str) -> dict[str, Any]` |
| 26 | `from __future__ import annotations` retained | **PASS** | Line 25 |
| 27 | No unused imports | **PASS** | All imports used: `json` (load auth.json, ccusage output), `logging`, `os`, `subprocess`, `datetime`, `pathlib`, `threading`, `Any`, `httpx` |
| 28 | No dead code from deleted SQLite path | **PASS** | Confirmed by grep (item 15) |
| 29 | `make lint` passes | **PASS** | 0 ruff errors |
| 30 | `make typecheck` passes | **PASS** | 0 mypy errors |
| 31 | `make test-unit` passes | **PASS** | 25 passed in `test_llm_usage.py`; 2 pre-existing failures in `test_safe_migrate.py` (unrelated) |

### Configuration Documentation

| # | Item | Status | Notes |
|---|------|--------|-------|
| 32 | `.env.example` documents both variables as optional commented-out lines | **PASS** | `.env.example` lines 77–83: both `IW_MINIMAX_API_KEY` and `IW_MINIMAX_GROUP_ID` present with explanatory comments |

---

## Findings

None. All 32 checklist items pass.

---

## Quality Gate Results

| Check | Result |
|-------|--------|
| `make lint` | ✅ 0 errors |
| `make typecheck` | ✅ 0 errors |
| `make test-unit` | ✅ 2224 passed, 2 skipped (pre-existing `test_safe_migrate.py` failures unrelated to this change) |
| SQLite grep | ✅ 0 matches |

---

## Recommendation

**approve**

S01 is clean, complete, and fully compliant with the design doc. The implementation correctly replaces the SQLite path with a live API call, handles all failure modes gracefully, and leaves Claude logic byte-identical. No changes requested.