# CR-00030_S04_CodeReview_prompt

**Work Item**: CR-00030 -- Show remaining time (not end time) on Claude 5h usage slot
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00030 --json`.
- `ai-dev/active/CR-00030/CR-00030_CR_Design.md`
- `ai-dev/active/CR-00030/reports/CR-00030_S03_Tests_report.md`
- `tests/unit/test_llm_usage.py`

## Output Files

- `ai-dev/active/CR-00030/reports/CR-00030_S04_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in `tests/unit/test_llm_usage.py` → CRITICAL findings.

## Review Checklist

### 1. Coverage

Verify the new `TestFormatRemainingFromTs` class has, at minimum:

| Branch | Required test |
|--------|---------------|
| `resets_at == 0` → `None` | yes |
| `resets_at` in past → `None` | yes |
| `<1 minute` → `"0m"` | yes |
| `<1 hour, >0 minutes` → `"<M>m"` | yes |
| `>=1 hour` (clean) → `"<H>h <M>m"` | yes |
| `>=1 hour` with seconds (drops them) | yes |

A missing branch is HIGH (test coverage gap).

### 2. AC traceability

Map each acceptance criterion AC1..AC6 from the design to at least one test:
- AC1 (5h shape) → strengthened `test_claude_usage_uses_seven_day_from_cache` (regex assert).
- AC2 (7d shape unchanged) → strengthened same test (week_reset has `:`).
- AC3 (sub-hour minutes only) → `test_under_one_hour_returns_minutes_only`.
- AC4 (sub-minute → `"0m"`) → `test_under_one_minute_returns_zero_m`.
- AC5 (expired/missing → None) → `test_past_returns_none`, `test_zero_returns_none`, **plus** `test_claude_usage_zero_when_cache_missing` (already in file, untouched — note in your review).
- AC6 (percentages untouched) → existing assertions in `test_claude_usage_uses_seven_day_from_cache` (`block_pct == 70`, `week_pct == 56`) cover this.

A missing AC mapping is HIGH.

### 3. Scope discipline

S03 should have modified ONLY `tests/unit/test_llm_usage.py`. Any other file touched (especially `orch/llm_usage.py`) is a CRITICAL scope violation.

### 4. Style and isolation

- No use of `importlib.reload(orch.config)` (project hard rule). CRITICAL if present.
- No live-DB connection — these tests are pure-function tests; no `pg_engine` / `db_session` fixture should appear.
- Tests don't share mutable global state — each test is self-contained.
- No flaky `datetime.now()` boundaries — assertions on `"25m"` should be safe at any wall-clock instant; if a test uses `60 * 60` exactly the second-rounding may flip between `"59m"` and `"1h 0m"`. Flag as MEDIUM_FIXABLE if the test cushion is < 5s.

### 5. Did NOT touch

- `TestFormatResetsAt`, `TestFormatReset`, `TestNoCcusageRegressions`, `TestNoSqliteRegressions`, `TestMinimaxUsageRemote`, `TestMinimaxUsage`, `TestCacheTTL`, `TestGetLlmUsageShape` — all must be unchanged. Edits to any of them are CRITICAL scope creep.

### 6. Strengthened test direction

`test_claude_usage_uses_seven_day_from_cache` — verify the new assertions are *stronger*, not weaker, than before. Specifically:
- Old `block_reset is not None` should still be implied (a regex-matching string is non-None). OK.
- Removing the `block_pct == 70` / `week_pct == 56` assertions is CRITICAL.

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit`. All tests pass. Report faithfully.

## Severity Levels

(Standard table.)

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00030",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
