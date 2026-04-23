# I-00034 S10: QV Integration Tests Gate

## What was done
Executed `make test-integration` as the integration-tests quality gate.

## Results

**Status: FAIL**

- **2 failed tests** (migration-related, pre-existing)
- **352 errors** (all caused by DB instance identity mismatch in dashboard app lifespan)
- **455 passed**

### Primary Failure Cause

The dashboard app's lifespan startup fails with:
```
orch.db.identity.InstanceMismatchError: DB instance-identity MISMATCH.
  Expected: 518ac56a-36f7-4c43-8f53-cfbb8a6baa3e   (from IW_CORE_EXPECTED_INSTANCE_ID)
  Actual  : 08446ded-daba-4e08-9721-3046dc68efa0   (from iw_core_instance.instance_id)
```

This causes all tests that bootstrap the FastAPI app (via `dashboard.app:app` or any router that imports it) to error during fixture setup. Only tests that avoid the app entirely (e.g., pure DB/model tests) pass.

### Pre-existing Failures (not introduced by this work item)

1. `test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid` — migration downgrade doesn't actually drop the `iw_core_instance` table
2. `test_downgrade_and_upgrade_round_trip` — same issue

## Files Changed
None (this is a read-only test execution).

## Observations
- The identity mismatch is an environment/configuration issue, not a code bug
- The 2 migration test failures are pre-existing and unrelated to I-00034
- The 352 errors are all downstream of the identity check in the dashboard lifespan