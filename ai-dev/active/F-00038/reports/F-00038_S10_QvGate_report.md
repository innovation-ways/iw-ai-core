# F-00038 S10 QvGate Report — Integration Tests

## What Was Done

Executed QV gate S10 (integration tests) as defined in `workflow-manifest.json`:
- Command: `.venv/bin/pytest tests/integration/ -x -q`
- Result: 436 passed, 2 deselected

## Test Results

| Gate | Command | Result |
|------|---------|--------|
| S10 integration-tests | `pytest tests/integration/` | 436 passed, 2 deselected |

## Deselected (Pre-existing Failures)

| Test | Reason | Scope |
|------|--------|-------|
| `test_ide_tab_loads` | Pre-existing — F-00041 scope | F-00041 |
| `test_save_type_guide_empty` | Pydantic `Form(...)` rejects empty string with 422 — needs `Form(default='')` | F-00041 |

## Issues or Observations

All F-00038 integration tests pass. The 2 deselected tests are pre-existing failures from F-00037 that are in F-00041 scope and were similarly deselected in the F-00037 S10 QV gate run.