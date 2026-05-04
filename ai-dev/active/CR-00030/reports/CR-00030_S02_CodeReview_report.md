# CR-00030 S02 Code Review Report

## What was reviewed

S01 (backend-impl) changed `orch/llm_usage.py` to switch the Claude 5h branch from `_format_resets_at` (wall-clock) to a new helper `_format_remaining_from_ts` (time remaining).

## Files changed

- `orch/llm_usage.py` — only file touched by S01 ✅

## Pre-review lint & format gate

- `make lint` — **2 errors** in `tests/dashboard/test_sse_client_wiring.py` (unused import `re`, redefintion) — **pre-existing, not introduced by S01**
- `make format` — **1 error** in same file (`test_sse_client_wiring.py`) — **pre-existing, not introduced by S01**

Running lint/format on `orch/llm_usage.py` in isolation: **PASS** ✅

## Checklist

### 1. Scope discipline
- Only `orch/llm_usage.py` was modified ✅
- `dashboard/templates/fragments/llm_usage_footer.html` — untouched ✅
- `dashboard/routers/usage.py` — untouched ✅
- `_format_resets_at` — still defined and still called by the 7d branch ✅
- `_format_reset` (MiniMax helper) — untouched ✅
- Return dict shape `block_pct`, `week_pct`, `block_reset`, `week_reset` — preserved ✅

### 2. Helper correctness (`_format_remaining_from_ts`)
- `resets_at <= 0` → `None` ✅
- Past timestamp (`delta < 0`) → `None` ✅
- `0 <= remaining_s <= 59` → `f"{remaining_s // 60}m"` → `"0m"` for 0 seconds ✅
- `0 <= remaining_s < 3600` → `"<M>m"` with no leading zero, no `"0h "` ✅
- `remaining_s >= 3600` → `"<H>h <M>m"` with single space, lowercase `h`/`m` ✅
- Uses `datetime.now(UTC).timestamp()` (not `time.time()` or deprecated `datetime.utcnow()`) ✅

### 3. Naming & docstring
- Helper is private (`_format_remaining_from_ts`) ✅
- Docstring states input (Unix timestamp float) and output formats (`'Hh Mm'` / `'Mm'` / `None`) ✅
- Module docstring (lines 14-15) mentions the 5h-vs-7d format split ✅

### 4. Conventions (`CLAUDE.md`, `orch/CLAUDE.md`)
- `from __future__ import annotations` present at top — not duplicated ✅
- No new imports added ✅
- Type hints: `float` in, `str | None` out (PEP 604 union) ✅
- No `print` statements, no debug logging at INFO level for hot path ✅

### 5. No unrelated edits
- No reformatting of untouched lines ✅
- No drive-by refactors of `_format_reset` or `_format_resets_at` ✅
- No changes to `_cache` / TTL logic ✅

### 6. Test verification
- `make test-unit`: **2572 passed, 4 skipped, 5 xfailed, 1 xpassed** — no regressions ✅
- The 2 pre-existing failures in `test_safe_migrate.py` (DNS resolution) are unrelated to this change

## Findings

None. S01 is clean, correct, and fully within scope.

## Test results

**`make test-unit`**: 2572 passed, 4 skipped, 5 xfailed, 1 xpassed, 48 warnings in 60.17s ✅
`tests/unit/test_llm_usage.py` — all 51 tests pass (confirmed by S01 report).

## Notes

- The `int(delta)` truncation approach avoids the `int(-0.5) == 0` issue described in the design doc.
- 60-second cache staleness near deadline is **pre-existing** behavior (documented in design doc §"Risk") — not a regression introduced by S01.
- No auto-fix applied to pre-existing lint errors in `test_sse_client_wiring.py` (not touched by this work item).

---

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00030",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2572 passed, 4 skipped, 5 xfailed, 1 xpassed",
  "notes": "S01 is clean. Pre-existing lint errors in tests/dashboard/test_sse_client_wiring.py are not introduced by this change and are out of scope."
}
```