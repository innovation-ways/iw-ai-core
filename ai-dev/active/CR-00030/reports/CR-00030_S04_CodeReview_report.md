# CR-00030 S04 Code Review Report

## What was reviewed

S03 (tests-impl): Unit tests for `_format_remaining_from_ts` + strengthened assertions in `test_claude_usage_uses_seven_day_from_cache`.

## Files changed

- `tests/unit/test_llm_usage.py` — added `import re`, new `TestFormatRemainingFromTs` class (8 test cases), strengthened `block_reset` / `week_reset` assertions in `test_claude_usage_uses_seven_day_from_cache`

## Pre-flight lint & format

- `tests/unit/test_llm_usage.py` passes ruff cleanly — `import re` is correctly placed at line 16 (needed for the regex assertions)
- `make lint` / `make format` failures are in `tests/dashboard/test_sse_client_wiring.py` — pre-existing issue, not modified by this step, confirmed in S03 report

## Coverage checklist — `TestFormatRemainingFromTs`

| Branch | Test | Status |
|--------|------|--------|
| `resets_at == 0` → `None` | `test_zero_returns_none` | ✓ |
| `resets_at` in past → `None` | `test_past_returns_none` | ✓ |
| `<1 minute` → `"0m"` | `test_under_one_minute_returns_zero_m` | ✓ |
| `<1 hour, >0 minutes` → `"<M>m"` | `test_under_one_hour_returns_minutes_only`, `test_under_one_hour_at_boundary` | ✓ |
| `>=1 hour` (just over boundary, +5s cushion) | `test_just_over_one_hour` (`now + 3600 + 5`) | ✓ |
| `>=1 hour` with seconds (drops them) | `test_multiple_hours_with_seconds` (`2h 43m 49s`) | ✓ |
| Multi-hour with non-boundary minutes | `test_multiple_hours` (`4h 32m 5s`) | ✓ |

## AC traceability

| AC | Mapping | Test(s) |
|----|---------|---------|
| AC1 (5h remaining-time shape) | `test_claude_usage_uses_seven_day_from_cache`: `re.fullmatch(r"\d+h \d+m\|\d+m", result["block_reset"])`, `":" not in result["block_reset"]` | ✓ |
| AC2 (7d wall-clock unchanged) | Same test: `":" in result["week_reset"]` | ✓ |
| AC3 (sub-hour minutes only) | `test_under_one_hour_returns_minutes_only`, `test_under_one_hour_at_boundary` | ✓ |
| AC4 (sub-minute → `"0m"`) | `test_under_one_minute_returns_zero_m` | ✓ |
| AC5 (expired/missing → None) | `test_past_returns_none`, `test_zero_returns_none`, `test_claude_usage_zero_when_cache_missing` (existing) | ✓ |
| AC6 (percentages untouched) | `block_pct == 70`, `week_pct == 56` assertions retained in strengthened test | ✓ |

## Scope discipline

- S03 modified only `tests/unit/test_llm_usage.py` (confirmed via `git diff --name-only`)
- No other files touched

## Style and isolation

- No `importlib.reload(orch.config)` used in new tests — `_format_remaining_from_ts` called directly without module reload
- No `pg_engine` / `db_session` fixtures in the file (pure function tests)
- All boundary offsets use 5-second cushions — safe from `int()` truncation flakiness
- Untouched test classes confirmed: `TestFormatResetsAt`, `TestFormatReset`, `TestNoCcusageRegressions`, `TestNoSqliteRegressions`, `TestMinimaxUsageRemote`, `TestMinimaxUsage`, `TestCacheTTL`, `TestGetLlmUsageShape`

## Strengthened assertions verification

- Old: `assert result["block_reset"] is not None` (non-None check only)
- New: `re.fullmatch(r"\d+h \d+m|\d+m", result["block_reset"])` — regex enforces new remaining-time shape — **stronger** ✓
- New: `assert ":" not in result["block_reset"]` — negative check for wall-clock format — **stronger** ✓
- `block_pct == 70` / `week_pct == 56` assertions **retained** — no regression ✓

## Test results

- `tests/unit/test_llm_usage.py`: **59 passed, 0 failed**
- `make test-unit` on full suite (reported by S03): **2580 passed, 4 skipped, 5 xfailed, 1 xpassed, 0 failed** (pre-existing xpassed unrelated to this change)

## Verdict

**PASS** — All coverage branches present, all ACs mapped, no scope violations, no `importlib.reload(orch.config)`, no live DB connections, strengthened assertions are genuinely stronger, boundary cushions are adequate (5s).
