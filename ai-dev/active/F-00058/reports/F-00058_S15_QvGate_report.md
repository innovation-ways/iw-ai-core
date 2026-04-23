# F-00058 S15: QvGate Integration Tests Report

## Gate
- **Gate**: integration-tests
- **Command**: `make test-integration`
- **Result**: FAIL

## Summary
Ran full integration test suite. **45 tests failed, 859 passed, 7 skipped, 14 errors**.

## Key Failure Patterns
Most OSS-related tests fail with `relation "oss_scan" does not exist` or `relation "project_oss_job" does not exist`. This indicates missing tables in the test database schema — likely tables `oss_scan` and `project_oss_job` are not being created during the test bootstrap.

## Test Results
| Metric | Count |
|--------|-------|
| Failed | 45 |
| Passed | 859 |
| Skipped | 7 |
| Errors | 14 |
| Duration | 168.16s |

## Failed Test Categories
- OSS boundary/dashboard/SSE/service tests — missing `oss_scan` and `project_oss_job` tables
- Migration tests — missing `oss_scan` table
- Project cascade tests — OSS FK constraints
- CLI tests — OSS-related
- Code index tests — some failures (thread exceptions)
- Agent constraints coverage — migration policy test

## Root Cause
The `oss_scan` and `project_oss_job` tables appear to be missing from the test schema. This is likely a migration ordering issue or a missing migration for these OSS-related tables.

## Recommendation
Investigate migration files to ensure `oss_scan` and `project_oss_job` tables are included in the test database setup. Check if these are recent tables that were added but migration not applied to testcontainers.
