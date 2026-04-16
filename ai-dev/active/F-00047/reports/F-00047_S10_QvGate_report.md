# F-00047 S10 QvGate Report

## What was done
Ran the integration test suite (`tests/integration/`) with Allure reporting enabled.

## Test Results
- **Total tests**: 479
- **Passed**: 479
- **Failed**: 0
- **Warnings**: 15 (deprecation warnings only, all non-blocking)
- **Duration**: 28.97s

## Files Changed
None — this was a quality gate verification step.

## Issues or Observations
All integration tests pass. The warnings are deprecation notices from third-party libraries (llama_index, starlette, asyncio) and SQLAlchemy SAWarnings related to transaction handling in specific test cases — none indicate functional failures.
