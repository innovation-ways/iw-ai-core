# F-00061 S14 — QV Gate Report: integration-tests

## Gate
- **Command**: `make test-integration`
- **Result**: FAIL (exit code 1)

## Summary
942 tests passed, 1 failure, 4 errors.

All failures/errors are in `tests/integration/test_f00055_workflow_fixture.py` — tests for F-00055 seed fixtures. They are **not** related to F-00061's implementation. The root cause is environmental: the `e2e_seed` guardrail in `scripts/e2e_seed.py:404` exits with code 2 when `IW_CORE_EXPECTED_INSTANCE_ID` is set but `IW_E2E_SEED` is not.

## Failures

| Test | Error |
|------|-------|
| `test_seed_is_idempotent` | `SystemExit: 2` — guardrail triggered |
| `test_fixture_seeds_18_workflow_steps_for_f00055` | setup ERROR — guardrail |
| `test_fixture_encodes_correct_retry_counts` | setup ERROR — guardrail |
| `test_fixture_seeds_fix_cycles_for_retry_steps` | setup ERROR — guardrail |
| `test_execution_report_returns_expected_hotspots` | setup ERROR — guardrail |

## Root Cause
The `.env` has `IW_CORE_EXPECTED_INSTANCE_ID` set (production DB pin), but `IW_E2E_SEED=1` is not set. The seed guardrail intentionally prevents running the e2e seed script against a production-like DB. This is a pre-existing environmental issue unrelated to F-00061.

## Files Changed
None — no code changes were made.

## Observations
- All 942 other integration tests pass cleanly.
- The failing tests are for F-00055 (a different work item), not F-00061.
- The guardrail is working as designed — it is correctly protecting production data.
- To resolve: either unset `IW_CORE_EXPECTED_INSTANCE_ID` for local test runs, or set `IW_E2E_SEED=1` when running these specific tests against a non-production DB.
