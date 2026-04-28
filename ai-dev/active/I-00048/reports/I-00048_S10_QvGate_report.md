# I-00048 S10 QvGate Report

## Gate: integration-tests
**Command**: `make allure-integration`
**Result**: FAIL

## Summary

Ran full integration test suite via `make allure-integration`. Exit code 1 due to 5 failing tests.

## Test Results

- **Passed**: 1129
- **Failed**: 5
- **Skipped**: 11
- **Warnings**: 153
- **Duration**: ~4 minutes (240.99s)

## Failing Tests (5)

All failures are in `tests/integration/test_cli_core.py` — all related to the `approve`/`unapprove` CLI commands expecting `ai-dev/active/{item_id}/` directory to exist:

| Test | Error |
|------|-------|
| `test_approve_draft_to_approved` | `Active directory not found: ai-dev/active/I-00001/. Create the design doc and prompts before approving.` |
| `test_approve_json_output` | Same — exit code 1 |
| `test_unapprove_approved_to_draft` | `Cannot unapprove: current status is 'draft'` (approve failed so item is still draft) |
| `test_unapprove_completed_batch_is_ok` | Same — approve step failed |
| `test_full_flow_next_id_register_approve` | Same — approve step failed |

## Root Cause

The tests call `approve` without first creating the `ai-dev/active/I-00001/` directory with design doc and prompts. This appears to be a regression — the tests may have previously worked if the `approve` command had different behavior, or the test setup is missing a fixture step.

## Files Changed

None — this is a test execution step, no code changes made.

## Observations

- The 5 failures are all CLI approve/unapprove tests that assume design doc directory exists
- 1129 other integration tests pass successfully
- The failures are consistent — approve fails because `ai-dev/active/I-00001/` is not created by the test