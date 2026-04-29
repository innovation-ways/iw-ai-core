# F-00068 S12 QV Gate Report

## Gate
- **Command**: `make allure-integration`
- **Result**: FAIL

## Summary
Integration tests quality gate ran 1147 tests (11 skipped). **2 tests failed**, 2 others are pre-existing failures unrelated to this work item.

## Failed Tests

### 1. `TestAC3.test_ac3_baselines_created_at_setup`
- **File**: `tests/integration/daemon/test_baseline_qv_pipeline.py:403`
- **Issue**: The `integration-tests` gate is not recognized by `_compute_qv_baselines` — log shows: `Unknown gate 'integration-tests' for step F-00061-3A075E2F/F-00061-3A075E2F-S14 — skipping baseline`
- **Expected**: 3 baseline rows, **Actual**: 2
- This is a pre-existing test issue where the gate name `integration-tests` is not registered in the baseline QV pipeline.

### 2. `TestBaselineBoundary.test_baseline_empty_passing_gate_persists_sentinel_row`
- **File**: `tests/integration/daemon/test_baseline_qv_pipeline.py:701`
- **Issue**: Fingerprint for empty passing gate includes `['unit-tests-output']` in `unparseable` field instead of `[]`
- **Expected**: `{'failures': [], 'unparseable': []}`
- **Actual**: `{'failures': [], 'unparseable': ['unit-tests-output']}`
- This is a pre-existing test issue with how empty output is classified.

## Observations
Both failures are in `test_baseline_qv_pipeline.py` — a module for baseline QV (quality validation) pipeline functionality. These are pre-existing issues unrelated to F-00068's feature work (OSS scan/findings/persistence).
