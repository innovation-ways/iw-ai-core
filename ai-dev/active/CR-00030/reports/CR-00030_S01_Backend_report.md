# CR-00030 S01 Backend Report

## What was done

Added `_format_remaining_from_ts`, switched the Claude 5h branch in `_claude_usage()` to use it, and updated the module docstring.

### Changes to `orch/llm_usage.py`

1. **New helper `_format_remaining_from_ts`** (lines 73–90):
   - Takes a Unix timestamp float, returns `str | None`
   - Computes `delta = resets_at - datetime.now(UTC).timestamp()` first, then truncates with `int()` — avoids the `int(-0.5) == 0` truncation issue described in the prompt
   - `>= 3600s` → `f"{hours}h {minutes}m"`; `< 3600s` → `f"{remaining_s // 60}m"`
   - Returns `None` for `resets_at <= 0` or when `delta < 0`

2. **Switched 5h branch** (line 128):
   - Before: `block_reset = _format_resets_at(five_hour.get("resets_at", 0))`
   - After: `block_reset = _format_remaining_from_ts(five_hour.get("resets_at", 0))`
   - 7d branch unchanged: `week_reset = _format_resets_at(seven_day.get("resets_at", 0))`

3. **Updated module docstring** (line 14):
   - Added: `The 5h label shows time remaining until reset (e.g. "4h 32m", "25m"); the 7d label shows a wall-clock reset time (e.g. "15:00" or "Tue 09:00").`

### Not touched (per prompt)
- `dashboard/templates/fragments/llm_usage_footer.html` — unchanged
- `dashboard/routers/usage.py` — unchanged
- `_format_reset` (MiniMax helper) — unchanged
- `_format_resets_at` — kept intact, 7d branch still uses it
- 60-second `_cache` TTL — unchanged

## Files changed

- `orch/llm_usage.py`

## Test results

- `tests/unit/test_llm_usage.py`: **51 passed**, 0 failed
  - `test_claude_usage_uses_seven_day_from_cache` passes (still asserts `block_reset is not None`; shape is now a remaining-time string)
  - All 51 llm_usage tests pass
- `make test-unit` overall: **2570 passed, 2 failed**
  - The 2 failures (`test_apply_refuses_in_agent_context`, `test_rollback_refuses_in_agent_context`) are pre-existing in `tests/unit/test_safe_migrate.py` — unrelated to this change, failed due to DNS resolution issue in the test environment
  - The `test_llm_usage.py` suite is clean

## Preflight

- **format**: `ok` — `orch/llm_usage.py` passes `ruff format --check`
- **typecheck**: `ok` — `mypy orch/llm_usage.py` reports no issues
- **lint**: `ok` — `ruff check orch/llm_usage.py` reports no issues

Note: `make format` and `make lint` show errors in `tests/dashboard/test_sse_client_wiring.py` (pre-existing, unrelated to this change).

## Notes

- `_format_remaining_from_ts` uses `delta < 0` (not `<=`) to return `None` for past timestamps, and `remaining_s == 0` renders as `"0m"` per the design spec
- The 60-second cache TTL staleness near deadline is pre-existing behavior, not introduced by this change