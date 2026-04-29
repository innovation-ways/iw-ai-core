# QV Gate Report: S10 — integration-tests

**Gate**: `make allure-integration`
**Result**: FAIL (3 failures out of 1159 tests)

## Summary

3 integration tests failed:

### 1. `TestAC3::test_ac3_baselines_created_at_setup`
**File**: `tests/integration/daemon/test_baseline_qv_pipeline.py:403`
**Error**: `assert 2 == 3` — only 2 QvBaseline rows created instead of 3
**Root cause**: Gate `integration-tests` is not recognized by `_compute_qv_baselines`:
```
WARNING orch.daemon.batch_manager:batch_manager.py:664 [F-00061] Unknown gate 'integration-tests' for step F-00061-92F0F15D/F-00061-92F0F15D-S14 — skipping baseline
```

### 2. `TestBaselineBoundary::test_baseline_empty_passing_gate_persists_sentinel_row`
**File**: `tests/integration/daemon/test_baseline_qv_pipeline.py:701`
**Error**: Expected `fingerprint == {"failures": [], "unparseable": []}` but got `{"failures": [], "unparseable": ["unit-tests-output"]}`
**Root cause**: Empty gate output still captures a file named `unit-tests-output` as unparseable.

### 3. `test_project_doc_fts_full_text_search`
**File**: `tests/integration/test_project_docs.py:486`
**Error**: `assert 3 == 1` — FTS search for "API" returned 3 results instead of 1
**Root cause**: `plainto_tsquery('english', 'API')` matches all docs since "Architecture Overview" contains "API" in its content too.

## Test Results

| Metric | Value |
|--------|-------|
| Passed | 1156 |
| Failed | 3 |
| Skipped | 11 |
| Duration | 4m 41s |

## Files Changed

No files were modified by this step — this was a pure execution of existing tests.

## Observations

1. The `integration-tests` gate is not registered in the baseline QV pipeline (`_compute_qv_baselines`). This appears to be a gap in gate handling.
2. The empty gate sentinel row test expects no `unit-tests-output` file in `unparseable`, but the parser is picking one up.
3. The FTS test uses data that overlaps across documents ("API" appears in multiple doc contents).
