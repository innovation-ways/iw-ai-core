# F-00066 S12 — QV Gate Report: integration-tests

## Gate
- **Command**: `make test-integration`
- **Exit code**: 1

## Result: FAIL

## Summary
Ran the full integration test suite. 2 pre-existing test failures were found, both in `tests/integration/daemon/test_baseline_qv_pipeline.py`. These failures are unrelated to F-00066's changes — they are test bugs in the baseline QV pipeline itself.

## Failures

### 1. `TestAC3.test_ac3_baselines_created_at_setup`
- **File**: `tests/integration/daemon/test_baseline_qv_pipeline.py:403`
- **Issue**: Test expects 3 `QvBaseline` rows created (lint, unit-tests, integration-tests gates) but only 2 were created.
- **Root cause**: The `integration-tests` gate is unknown to the baseline system — log shows `WARNING ... Unknown gate 'integration-tests' for step ... — skipping baseline`
- **Classification**: Pre-existing test bug (gate name not registered in the baseline QV gate registry)

### 2. `TestBaselineBoundary.test_baseline_empty_passing_gate_persists_sentinel_row`
- **File**: `tests/integration/daemon/test_baseline_qv_pipeline.py:701`
- **Issue**: Test expects fingerprint `{"failures": [], "unparseable": []}` for an empty passing gate, but got `{"unparseable": ["unit-tests-output"]}`
- **Root cause**: The empty output is being treated as an unparseable file named "unit-tests-output" rather than as genuinely empty passing output
- **Classification**: Pre-existing test bug (fingerprint computation for empty output)

## Test Stats
- **Total**: 1147 passed, 2 failed, 11 skipped
- **Duration**: 252.63s (4m 12s)

## Files Changed
None — this step only ran existing tests.

## Observations
The 2 failing tests are in the baseline QV pipeline test suite (`test_baseline_qv_pipeline.py`) and represent known/pre-existing issues with how that pipeline handles gate names and empty output fingerprints. They are not regressions introduced by F-00066.
