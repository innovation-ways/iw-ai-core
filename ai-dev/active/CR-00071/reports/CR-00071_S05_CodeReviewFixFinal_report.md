# CR-00071 S05 Code Review Fix Final Report

**Step**: S05 — Code Review Fix Final
**Agent**: code-review-fix-final-impl
**Work Item**: CR-00071 — Pi Runtime Context-Usage Percentage Support
**Completion Status**: complete
**Date**: 2026-05-21

---

## What Was Done

S04 returned **"pass"** with **zero mandatory findings** (no CRITICAL, HIGH, or
MEDIUM_FIXABLE). As S05, this agent performed a systematic code audit to verify
the implementation was actually present on disk — and discovered the S01
implementation was **missing from the committed branch**.

The `normalize_pi_messages()` function was not in `orch/chat/context_usage.py`
and the import was not in `tests/unit/test_context_usage.py`. This agent:

1. **Added `normalize_pi_messages()`** to `orch/chat/context_usage.py`
2. **Added `normalize_pi_messages` to the import** in
   `tests/unit/test_context_usage.py`
3. **Added `TestNormalizePiMessages`** (7 test cases) to
   `tests/unit/test_context_usage.py`
4. Fixed 2 ruff lint issues in the new test methods:
   - `test_translates_cacheRead_cacheWrite_to_cache_read_write` → renamed to
     `test_translates_cache_read_cache_write_fields` (N802: snake_case required)
   - Long line split across two lines (E501: line > 100 chars)

---

## Findings Fixed

| ID | Description | Fix Applied |
|----|-------------|-------------|
| — | `normalize_pi_messages()` absent from `orch/chat/context_usage.py` | Added function (55 lines) between the imports and `compute_context_pct()` |
| — | `normalize_pi_messages` absent from test imports in `tests/unit/test_context_usage.py` | Added to the `from orch.chat.context_usage import (...)` block |
| — | `TestNormalizePiMessages` (7 tests) absent from `tests/unit/test_context_usage.py` | Added class covering: none/non-list input, non-dict messages, usage→tokens translation, camelCase→snake_case cache fields, field preservation, absent usage |
| N802 | Test method name `test_translates_cacheRead_cacheWrite_to_cache_read_write` used camelCase | Renamed to `test_translates_cache_read_cache_write_fields` |
| E501 | Long line (>100 chars) in test case | Split across two lines |

---

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `orch/chat/context_usage.py` | +65 | Added `normalize_pi_messages()` pure helper + `_TokensShape` TypedDict |
| `tests/unit/test_context_usage.py` | +57 | Added `normalize_pi_messages` import + `TestNormalizePiMessages` class (7 cases) + assertion guard |

---

## Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ All checks passed |

---

## Test Results

```bash
$ uv run pytest tests/unit/test_context_usage.py -v --no-cov -q
39 passed in 0.24s

$ uv run pytest tests/dashboard/test_chat_router_pi.py -v --no-cov -q
12 passed in 10.36s

$ uv run pytest tests/integration/test_chat_tabs_api.py -v --no-cov -q -k "context_pct"
3 passed
```

---

## Subagent Result

```json
{
  "step": "S05",
  "agent": "code-review-fix-final-impl",
  "work_item": "CR-00071",
  "completion_status": "complete",
  "findings_fixed": [],
  "findings_skipped": [],
  "files_changed": [
    "orch/chat/context_usage.py",
    "tests/unit/test_context_usage.py"
  ],
  "tests_passed": true,
  "test_summary": "lint + format-check passed; 39 unit + 12 dashboard Pi + 3 integration tests passed",
  "blockers": [],
  "notes": "S04 returned pass with zero mandatory findings. This agent performed due-diligence code audit, discovered the normalize_pi_messages() implementation was absent from the committed branch, and added the missing implementation + tests. AC1–AC5 remain satisfied."
}
```