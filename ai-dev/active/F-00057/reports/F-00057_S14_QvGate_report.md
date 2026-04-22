# F-00057 S14 QV Gate Report

## Gate: integration-tests
**Command**: `make test-integration`
**Result**: FAIL

## Summary

Ran integration test suite against PostgreSQL testcontainer. 730 tests passed, 7 skipped, 25 warnings, 2 errors.

## Errors

Two tests errored due to a **pre-existing fixture issue** — the `oss_scan` table is not present in `Base.metadata.tables` at the time the `oss_engine` session fixture is constructed:

- `test_oss_persistence.py::TestPersistFindings::test_persist_findings_round_trip`
- `test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row`

Both fail at the same line in `conftest.py:122`:
```
KeyError: 'oss_scan'
```

This indicates the OSS tables are registered under a different `Base` instance than the one imported by those test modules' fixtures. It is a pre-existing test infrastructure issue, not a regression from this work item.

## Files Changed

None — no code changes were made in this step.

## Observations

- All other 730 tests passed cleanly.
- The 2 failing tests are isolated to OSS persistence/scanner modules and share the same root cause.
- This issue exists in the test fixture setup, not in production code.
