# F-00021 S11 QV Gate — Integration Tests Report

## Gate Details
- **Gate**: `integration-tests`
- **Tool**: `pytest`
- **Command**: `.venv/bin/pytest tests/integration/ -x -q`

## Result: PASS

418 integration tests passed in 16.31s with 3 warnings (SAWarning for transaction/flush operations in duplicate key tests — expected behavior).

## Notes
- The `--timeout` flag is not installed in this environment; tests were run without it
- All 418 tests passed successfully
- 3 SAWarning warnings related to transaction rollback in duplicate key constraint tests — these are expected

## Files Changed
None — this is a read-only gate step.