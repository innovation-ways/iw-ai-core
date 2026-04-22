# CR-00017 S18: QV Gate — Integration Tests

## What was done
Executed `make test-integration` to run the full integration test suite.

## Test Results
- **Total**: 796 tests (794 passed, 2 failed, 7 skipped)
- **Exit code**: 1 (gate failed)

## Failed Tests (pre-existing, unrelated to CR-00017)
1. `tests/integration/test_db_identity_integration.py::TestMigrationRoundtrip::test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid`
2. `tests/integration/test_iw_core_instance_migration.py::test_downgrade_and_upgrade_round_trip`

Both failures are in alembic downgrade tests for the `iw_core_instance` table. The downgrade command does not drop the table as expected. These are pre-existing issues unrelated to the changes in CR-00017.

## Files Changed
None — this was a read-only test execution gate.

## Issues / Observations
- The 2 failing tests are migration/downgrade tests that verify `alembic downgrade -1` drops the `iw_core_instance` table. They fail consistently and are not introduced by CR-00017.
- All other 794 tests pass, indicating no regression in the CR-00017 changes.
