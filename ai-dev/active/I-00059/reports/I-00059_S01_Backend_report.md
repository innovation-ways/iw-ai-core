# I-00059 S01 Backend Report

## Work Item
**I-00059** — Doc Generation Job Detail Page Shows No Error Info or Parameters

## Step
**S01** — Backend Implementation

## What Was Done

Fixed `_get_doc_generation` in `orch/jobs/aggregator.py` to return a `JobRow` whose `raw` dict contains the full set of diagnostic fields (error, skill_used, duration_seconds, doc_id, trigger_reason, etc.) instead of only 3 stub keys.

### Root Cause
The detail page route (`/project/{p}/jobs/doc_generation/{id}`) calls `JobsAggregator.get_job()` → `_get_doc_generation()`. That method was building `raw` as:
```python
raw={"id": job.id, "project_id": job.project_id, "status": job.status.value}
```
While `_fetch_doc_generation()` (list view) correctly built a 14-field dict with all diagnostic fields. The template read missing keys from `raw` — all `None` — so the page showed nothing useful.

### Fix Applied
1. **Extracted `_build_doc_generation_raw()` helper** — a private method that both `_fetch_doc_generation` (list view) and `_get_doc_generation` (detail page) now call, ensuring they can never drift again.
2. **Updated `_get_doc_generation`** to use `self._build_doc_generation_raw(job)` instead of the stub dict.

## Files Changed

| File | Change |
|------|--------|
| `orch/jobs/aggregator.py` | Added `_build_doc_generation_raw()` helper; `_get_doc_generation` now calls it |
| `tests/integration/test_i00059_doc_generation_get_job.py` | New integration test (TDD RED phase → GREEN) |

## Test Results

- `test_get_doc_generation_raw_contains_diagnostic_fields` — **PASSED**
- `test_get_doc_generation_raw_triggered_by_field` — **PASSED**
- All existing aggregator integration tests — **PASSED** (7 total)
- Pre-flight quality gates: format ✅, typecheck ✅, lint ✅

**Note**: 2 pre-existing unit test failures in `test_safe_migrate.py` (unrelated to this change; existed before).

## TDD Followed

1. **RED**: Wrote failing test `test_get_doc_generation_raw_contains_diagnostic_fields` asserting `error`, `skill_used`, `duration_seconds`, `doc_id`, `trigger_reason` all appear in `row.raw` — failed before fix.
2. **GREEN**: Applied fix to `_get_doc_generation` using extracted helper — test passed.
3. **REFACTOR**: Extracted `_build_doc_generation_raw()` private helper used by both callers, preventing future drift.