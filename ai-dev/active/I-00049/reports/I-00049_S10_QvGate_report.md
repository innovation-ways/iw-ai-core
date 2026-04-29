# I-00049 S10 QV Gate Report

## What was done
Executed `make allure-integration` as the integration-tests quality gate for work item I-00049.

## Test Results
- **Status**: FAIL
- **Passed**: 1146
- **Failed**: 3
- **Skipped**: 11
- **Duration**: 254.66s (4m 14s)

## Failed Tests

### 1. `TestAC3::test_ac3_baselines_created_at_setup`
**File**: `tests/integration/daemon/test_baseline_qv_pipeline.py:403`
**Error**: Assertion `assert len(rows) == 3` failed — only 2 QvBaseline rows created instead of 3.
**Root cause**: Log shows `Unknown gate 'integration-tests' for step F-00061-1E6F475B/F-00061-1E6F475B-S14 — skipping baseline`

### 2. `TestBaselineBoundary::test_baseline_empty_passing_gate_persists_sentinel_row`
**File**: `tests/integration/daemon/test_baseline_qv_pipeline.py:701`
**Error**: Sentinel fingerprint `{'unparseable': ['unit-tests-output']}` instead of expected `{'unparseable': []}`
**Root cause**: Empty output is being captured as an unparseable file instead of a passing sentinel.

### 3. `TestMergeQueueIntegration::test_merge_queue_oldest_first`
**File**: `tests/integration/test_batch_manager.py:419`
**Error**: Item status is `migration_rebase_failed` instead of `merged`
**Root cause**: `FileNotFoundError` in `_parse_migration` — subprocess stdout `"squash ok"` is being treated as a file path.

## Observations
1. The `integration-tests` gate is not recognized by `_compute_qv_baselines` — appears to be a gate name mapping issue (likely needs to be added to `GATE_KINDS` or equivalent).
2. The empty-output sentinel logic captures the literal string `"unit-tests-output"` as unparseable — incorrect handling when output is empty.
3. The merge queue test failure is a mocking issue — `fake_commit_script` returns `stdout="squash ok"` which is then parsed as a migration path.

These failures appear to be pre-existing test bugs, not regressions introduced by I-00049.