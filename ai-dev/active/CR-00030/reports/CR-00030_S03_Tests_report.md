# CR-00030 S03 Tests Report

## What was done

1. **Added `TestFormatRemainingFromTs`** (8 new test cases) immediately before `TestNoCcusageRegressions`, covering all branches of `_format_remaining_from_ts`:
   - `test_zero_returns_none`
   - `test_past_returns_none`
   - `test_under_one_minute_returns_zero_m`
   - `test_under_one_hour_returns_minutes_only`
   - `test_under_one_hour_at_boundary`
   - `test_just_over_one_hour`
   - `test_multiple_hours`
   - `test_multiple_hours_with_seconds`

2. **Strengthened `test_claude_usage_uses_seven_day_from_cache`** — added shape assertions after the existing `is not None` checks:
   ```python
   # 5h: must be remaining-time format, NEVER wall-clock "HH:MM"
   assert re.fullmatch(r"\d+h \d+m|\d+m", result["block_reset"])
   assert ":" not in result["block_reset"]

   # 7d: still wall-clock — must contain a colon
   assert ":" in result["week_reset"]
   ```

3. **Added `import re`** at the top of the test file.

## Files changed

- `tests/unit/test_llm_usage.py` (added `re` import, new `TestFormatRemainingFromTs` class, strengthened `block_reset` assertion in `test_claude_usage_uses_seven_day_from_cache`)

## Test results

- `tests/unit/test_llm_usage.py`: **59 passed, 0 failed**
  - All 8 new `TestFormatRemainingFromTs` cases pass
  - Strengthened `test_claude_usage_uses_seven_day_from_cache` passes
  - Pre-existing 51 tests unaffected
- `make test-unit` (all unit tests): **2580 passed, 4 skipped, 5 xfailed, 1 xpassed, 0 failed**

## Preflight

- **format**: pre-existing issue in `tests/dashboard/test_sse_client_wiring.py` (unrelated to this change, not modified)
- **typecheck**: `ok` — mypy reports no issues in `orch/` and `dashboard/`
- **lint**: pre-existing issue in `tests/dashboard/test_sse_client_wiring.py` (unrelated to this change, not modified)

## Notes

- No `importlib.reload(orch.config)` used — the new tests call `_format_remaining_from_ts` directly without reloading
- All boundary values in new tests use 5-second cushions to prevent race-condition flakiness
- `TestFormatResetsAt`, `TestFormatReset`, and other existing test classes are untouched