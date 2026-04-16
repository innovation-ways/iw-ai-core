# F-00049 S12 QV Gate Report

## What was done
Executed integration test suite with Allure reporting: `uv run pytest tests/integration/ -v --alluredir=allure-results`

## Test Results
- **Total tests**: 487
- **Passed**: 487
- **Failed**: 0
- **Skipped**: 0
- **Exit code**: 0

All integration tests passed successfully.

## Observations
- Some deprecation warnings observed (llama_index.table_names(), asyncio events) but these do not affect test validity
- SAWarning about transaction rollback on 3 tests is expected behavior for FK constraint tests
- All test modules executed without errors
