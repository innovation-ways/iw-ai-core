# F-00069 S12 QV Gate Report

## Gate: integration-tests
**Command**: `make allure-integration`
**Result**: FAIL (exit code 1)

## Summary

Ran the full integration test suite. 3 tests failed out of 1155 passed.

## Failed Tests

### 1. `TestAC3::test_ac3_baselines_created_at_setup`
**File**: `tests/integration/daemon/test_baseline_qv_pipeline.py:403`
**Error**: `assert len(rows) == 3` — got 2 rows instead of 3
**Root Cause**: The `integration-tests` gate is not recognized by `_compute_qv_baselines`. Log warning: `Unknown gate 'integration-tests' for step F-00061-D67680B7/F-00061-D67680B7-S14 — skipping baseline`

### 2. `TestBaselineBoundary::test_baseline_empty_passing_gate_persists_sentinel_row`
**File**: `tests/integration/daemon/test_baseline_qv_pipeline.py:701`
**Error**: Expected `unparseable: []` but got `['unit-tests-output']`
**Root Cause**: Sentinel baseline row for a passing gate incorrectly includes the output dir as unparseable.

### 3. `test_project_doc_fts_full_text_search`
**File**: `tests/integration/test_project_docs.py:486`
**Error**: `assert len(results) == 1` for query `'API'` — got 3 results instead of 1
**Root Cause**: FTS query on "API" is returning all docs that contain "API" (in content) but also matching docs whose content contains "API" as a substring (e.g., "REST API endpoints"). This is an FTS matching behavior issue.

## Test Results
- **Total**: 1155 passed, 3 failed, 11 skipped
- **Coverage**: 57% (required: 46%)
- **Duration**: ~6 minutes 32 seconds

## Observations

1. The `integration-tests` gate name is not registered in the baseline QV system — it only knows `lint`, `unit-tests`, and apparently something else. The gate name mismatch causes baseline computation to skip steps with `integration-tests` as the gate.

2. The baseline sentinel logic appears to incorrectly mark empty output directories as unparseable even when the gate command exits 0.

3. The FTS `plainto_tsquery('english', 'API')` is returning false positives because "API" appears as a substring in other words like "REST API".