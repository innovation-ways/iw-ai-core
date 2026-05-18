# I-00098 S04 CodeReview Tests Report

## What Was Reviewed

S03 (tests-impl) added regression tests for the I-00098 TZ-mismatch bug in `tests/integration/test_keep_alive_integration.py`. This review validates that the tests are fit-for-purpose: deterministic across `pytest-randomly` seeds, actually exercise the bug at the SQL level, and provide meaningful TZ-offset coverage.

## Files Changed (by S03)

| File | Change |
|------|--------|
| `tests/integration/test_keep_alive_integration.py` | Added `test_get_due_slots_skips_already_run_slot_across_utc_midnight` (4-case parametrized), added positive-control `test_get_due_slots_returns_slot_when_no_prior_run_exists`, added `freezegun` + `text` imports |
| `pyproject.toml` | Added `DTZ001` to `tests/**` per-file ignores (freezegun legitimately uses naive datetimes with `freeze_time`) |

Note: `pyproject.toml` is outside the design's `allowed_paths` (`orch/keep_alive_service.py` + `tests/integration/test_keep_alive_integration.py`), but the DTZ001 ignore is required for lint to pass with the freezegun pattern, and is targeted to `tests/**`. Documented; not a blocker.

## Pre-Flight Quality Gates (NON-NEGOTIABLE)

| Gate | Result |
|------|--------|
| `uv run ruff check tests/integration/test_keep_alive_integration.py` | ✅ PASS |
| `uv run ruff format --check tests/integration/test_keep_alive_integration.py` | ✅ PASS |

## Test Results

```
uv run pytest tests/integration/test_keep_alive_integration.py -v --no-cov
15 passed in 13.87s (randomly-seed=436098753)

uv run pytest tests/integration/test_keep_alive_integration.py --randomly-seed=12345 --no-cov -q
15 passed in 13.01s

uv run pytest tests/integration/test_keep_alive_integration.py --randomly-seed=67890 --no-cov -q
15 passed in 12.36s

uv run pytest tests/integration/test_keep_alive_integration.py --randomly-seed=11111 --no-cov -q
15 passed in 7.54s
```

All runs green under multiple seeds. No order-dependence detected.

## Review Findings

### Finding 1: Scope Adifference — pyproject.toml DTZ001 ignore

- **Severity**: LOW (advisory)
- **File**: `pyproject.toml`
- **Description**: S03 modified `pyproject.toml` to add `DTZ001` to `tests/**` per-file ignores. The design's `allowed_paths` lists only `orch/keep_alive_service.py` and `tests/integration/test_keep_alive_integration.py`. However: (a) the design itself acknowledges freezegun's naive-datetime pattern as legitimate, (b) the change is a minimal one-line per-file ignore targeted to `tests/**`, (c) without it `make lint` fails on the test file. The change is defensible on substance and does not affect production code.
- **Suggested fix**: None — accept as documented.
- **Category**: scope_adherence

## Acceptance Criteria Traceability

| AC | Test | Status |
|----|------|--------|
| AC1: Bug fixed in mismatch window | `test_get_due_slots_skips_already_run_slot_across_utc_midnight[WEST]` + `[CEST]` | ✅ PASS |
| AC2: Regression test exists | `test_get_due_slots_skips_already_run_slot_across_utc_midnight` in file | ✅ PASS |
| AC3: No regression in UTC | `test_get_due_slots_skips_already_run_slot_across_utc_midnight[UTC]` | ✅ PASS |

## TDD RED Evidence (from S03 report, verified against test)

The bug-exposing case `WEST` (+01:00) would fail pre-fix because:
- `today_date = datetime.now().date()` → `2026-05-18` (local)
- `func.date(fired_at)` → `2026-05-17` (UTC — session TZ defaults to UTC; `fired_at` re-stamped to `2026-05-17 23:30 UTC`)
- Filter `2026-05-17 == 2026-05-18` → false → `run_exists is None` → slot treated as due
- **Pre-fix assertion `assert due == []` would fail** — slot leaked through

Post-fix: `fired_at` falls inside the tz-aware half-open range `[2026-05-18 00:00 +01:00, 2026-05-19 00:00 +01:00)` and is correctly skipped.

## Notes

- The `EST` (-05:00) case is a symmetry/positive-control rather than a bug-exposing case: on a -05:00 host, `00:30 local = 05:30 UTC` same calendar day, so no prev-UTC-day mismatch exists and the slot is correctly skipped pre-fix. This is correctly documented in S03's report. Coverage is acceptable under the design's "if you can't make it reliable" clause.
- `monkeypatch.setenv("TZ", ...)` teardown is handled automatically by pytest's `MonkeyPatch` fixture — no TZ leakage between tests.
- No `importlib.reload(orch.config)` in the test file.
- No `-p no:randomly` override.

## Verdict

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00098",
  "step_reviewed": "S03",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [
    {
      "severity": "LOW",
      "category": "scope_adherence",
      "file": "pyproject.toml",
      "description": "DTZ001 ignore added outside design's allowed_paths, but targeted to tests/** and required for lint to pass with freezegun pattern.",
      "suggested_fix": "None — accept as documented."
    }
  ],
  "tests_passed": true,
  "test_summary": "15 passed, 0 failed (verified under 3 randomly seeds: 12345, 67890, 11111)",
  "notes": "The pyproject.toml DTZ001 ignore is outside the design's allowed_paths but defensible on substance. The EST case is a positive-control symmetry case rather than bug-exposing, which is correctly documented. No critical blockers."
}
```