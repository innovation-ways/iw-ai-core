# CR-00030_S03_Tests_prompt

**Work Item**: CR-00030 -- Show remaining time (not end time) on Claude 5h usage slot
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item touches no migrations.)

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00030 --json`.
- `ai-dev/active/CR-00030/CR-00030_CR_Design.md` — read **Acceptance Criteria** in full.
- `ai-dev/active/CR-00030/reports/CR-00030_S01_Backend_report.md`
- `orch/llm_usage.py` (after S01)
- `tests/unit/test_llm_usage.py` (existing test file — read top-to-bottom before editing)

## Output Files

- `ai-dev/active/CR-00030/reports/CR-00030_S03_Tests_report.md`
- Modified: `tests/unit/test_llm_usage.py`

## Context

Add unit-test coverage for the new `_format_remaining_from_ts` helper and tighten the one existing test that asserts on the 5h `block_reset` shape. Do NOT touch tests for `_format_reset` (MiniMax) or `_format_resets_at` (still used by 7d).

## Requirements

### 1. New test class `TestFormatRemainingFromTs`

Add a new test class next to `TestFormatResetsAt`, covering every branch of `_format_remaining_from_ts`. Mirror the style of `TestFormatReset` and `TestFormatResetsAt`.

Required cases:

- `test_zero_returns_none` — `_format_remaining_from_ts(0)` → `None`.
- `test_past_returns_none` — `_format_remaining_from_ts(now - 60)` → `None`.
- `test_under_one_minute_returns_zero_m` — `resets_at = now + 30` → `"0m"`.
- `test_under_one_hour_returns_minutes_only` — `resets_at = now + (25 * 60 + 5)` → `"25m"`.
- `test_under_one_hour_at_boundary` — `resets_at = now + (59 * 60 + 50)` → `"59m"` (well below the 3600s boundary so no flake risk).
- `test_just_over_one_hour` — `resets_at = now + (3600 + 5)` → `"1h 0m"` (5-second cushion above 3600 so the helper's `int()` truncation cannot tip the test back into the `<3600` branch).
- `test_multiple_hours` — `resets_at = now + (4 * 3600 + 32 * 60 + 5)` → `"4h 32m"` (5-second cushion past the 32-minute boundary).
- `test_multiple_hours_with_seconds` — `resets_at = now + (2 * 3600 + 43 * 60 + 49)` → `"2h 43m"` (seconds dropped; not on a boundary).

Use `datetime.now(UTC).timestamp() + offset` to construct test inputs. Do **not** use a clean boundary value like `+3600` or `+ (4 * 3600 + 32 * 60)` — by the time the helper computes `int(resets_at - datetime.now(UTC).timestamp())`, the elapsed wall-clock cost of test setup will tip `remaining_s` from N down to N-1, flipping the formatted result one minute backward (e.g. a `+3600` test would assert `"1h 0m"` but the helper would return `"59m"`). The 5-second cushions above eliminate the race. Do not freeze time globally — these tests are pure-function tests and the cushions are sufficient.

### 2. Tighten `TestClaudeRateLimitsCache::test_claude_usage_uses_seven_day_from_cache`

The existing test asserts `result["block_reset"] is not None`. Strengthen it:

```python
import re

# 5h: must be remaining-time format ("Xh Ym" or "Xm"), NEVER wall-clock "HH:MM"
assert re.fullmatch(r"\d+h \d+m|\d+m", result["block_reset"]), result["block_reset"]
assert ":" not in result["block_reset"]

# 7d: still wall-clock — must contain a colon
assert result["week_reset"] is not None
assert ":" in result["week_reset"]
```

Place these alongside the existing percentage assertions. Do not delete the old `is not None` assertions — strengthen them, do not weaken.

### 3. Do NOT touch

- `TestFormatResetsAt` — `_format_resets_at` is still used by the 7d branch; its tests must remain.
- `TestFormatReset` — unrelated MiniMax helper.
- `TestNoCcusageRegressions`, `TestNoSqliteRegressions` — unrelated.
- `TestMinimaxUsageRemote`, `TestMinimaxUsage`, `TestCacheTTL`, `TestGetLlmUsageShape` — unrelated.

If you find yourself editing any of those, stop — you are off-track.

## Project Conventions

Read `CLAUDE.md` and `tests/CLAUDE.md`. Hard rules that apply here:

- **NEVER** call `importlib.reload(orch.config)` — use `monkeypatch.delenv()` instead. (You won't need to reload anything for these tests; `_format_remaining_from_ts` is a pure function.)
- **NEVER** connect to live DB. (Not relevant for unit tests of a pure function — no DB usage.)
- Test names start with `test_` and read as English (`test_under_one_hour_returns_minutes_only`, not `test_lt_1h`).
- Use `pytest.MonkeyPatch` typing on fixtures where applicable; these tests should not need monkeypatching at all.
- Each test is a method of a single class (existing pattern in the file).

## TDD Requirement

These tests should be written first against a non-existent helper (RED), then S01's implementation makes them pass (GREEN). Since S01 runs before S03 in the orchestrator, by the time you arrive the helper exists — but you should still verify that:

1. The new tests pass against the current `_format_remaining_from_ts`.
2. If you temporarily revert the import (`from orch.llm_usage import _format_remaining_from_ts`) at the top of a test method or comment-out the helper, the tests would have failed — i.e. they actually exercise the new logic, not a tautology.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

```bash
make format
make typecheck
make lint
```

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit`. All `tests/unit/test_llm_usage.py` tests must pass — old and new. Report results faithfully.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "CR-00030",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_llm_usage.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
