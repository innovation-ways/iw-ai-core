# I-00098 S01 Backend Report

## What Was Done

Fixed the TZ-mismatch bug in `orch/keep_alive_service.py:get_due_slots()` that caused the keep-alive scheduler to re-fire successful slots around UTC midnight when the host's local timezone differs from UTC.

### Root Cause
The original filter used `func.date(KeepAliveRun.fired_at) == today_date` where:
- `today_date = datetime.now().date()` — naïve local calendar date
- `func.date()` on a TIMESTAMPTZ column evaluates in the DB session's `TimeZone` (UTC by default)

Around local midnight on a host in, e.g., WEST (+01:00), the two dates disagree: local sees `2026-05-18` but UTC sees `2026-05-17`, so successful runs from earlier today were not found.

### Fix Applied
Replaced the `func.date()` comparison with a **tz-aware half-open TIMESTAMPTZ range**:

```python
local_tz = datetime.now().astimezone().tzinfo
today_start_local = datetime.combine(today_date, time.min).replace(tzinfo=local_tz)
tomorrow_start_local = today_start_local + timedelta(days=1)

# In the filter:
KeepAliveRun.fired_at >= today_start_local,
KeepAliveRun.fired_at < tomorrow_start_local,
```

Both bounds are tz-aware (e.g., `2026-05-18 00:00:00+01:00` and `2026-05-19 00:00:00+01:00`), so PostgreSQL compares instants consistently regardless of the session's `TimeZone` setting.

### Additional Changes
- Added `time` to the `datetime` import line (line 12)
- Removed the now-unused `from sqlalchemy import func` import
- Updated the docstring comment to accurately describe the new tz-aware range semantics

## Files Changed

| File | Change |
|------|--------|
| `orch/keep_alive_service.py` | Replaced `func.date(...) == today_date` with `fired_at >= today_start_local AND fired_at < tomorrow_start_local`; added `time` import; removed unused `func` import; updated docstring |

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ All 750 files already formatted |
| `make typecheck` | ✅ Success: no issues found in 255 source files |
| `make lint` | ✅ All checks passed |
| `grep -rn 'func\.date' orch/ dashboard/` | ✅ Returns zero matches (audit confirmed) |

## Test Results

```
tests/unit/test_keep_alive_service.py: 9 passed
```

All existing unit tests pass. The coverage failure (3% total vs 50% threshold) is a pre-existing project configuration issue unrelated to this change.

## Scope Adherence

- ✅ Only `orch/keep_alive_service.py` modified
- ✅ No migrations touched (schema already correct)
- ✅ No other files changed
- ✅ Slot-time window logic (`[now - 30min, now]`) untouched
- ✅ Malformed `time_hhmm` try/except untouched
- ✅ `enabled == True` slot query untouched
- ✅ `status.in_(("success", "retried_success"))` predicate untouched

## Notes

- The fix is fundamentally correct: tz-aware bounds compared against a TIMESTAMPTZ column is the proper SQL pattern for calendar-day filtering across timezones.
- The design document notes this bug pattern could recur in future scheduler-style queries — worth adding a "TIMESTAMPTZ + naïve datetime.now()" entry to `tests/CLAUDE.md` Gotchas as a follow-up.
- S03 (tests-impl) owns the behavioural regression test; S01 is production-logic-only per the implementation prompt.