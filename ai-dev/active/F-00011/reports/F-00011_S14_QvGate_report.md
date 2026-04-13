# F-00011 S14 QV Gate Report — Integration Tests (Re-run)

**Date**: 2026-04-13
**Step**: S14
**Gate**: integration-tests (`make allure-integration`)
**Result**: PASS

## Summary

Ran `make allure-integration` which executes `uv run pytest tests/integration/ -v --alluredir=allure-results`. All 329 tests passed with 3 harmless SAWarnings (pre-existing, related to transaction/instance conflict in unique constraint tests).

## Test Results

```
$ make allure-integration
uv run pytest tests/integration/ -v --alluredir=allure-results
======================= 329 passed, 3 warnings in 11.32s =======================
```

## Files Changed

No files were modified. This step only runs existing integration tests.

## Observations

- All 329 integration tests passed
- 3 warnings are all SAWarnings related to SQLAlchemy transaction handling in unique constraint tests — pre-existing and harmless
- Test coverage includes: archive, artifact browser, batch management, browser verification flow, CLI commands/batches/core/steps, dashboard actions/fragments/pages/remaining, doc commands/service/routes, fix cycle, history sorting, init project, migration lock, models, project docs, search, and SSE events

## QV Gate Summary for F-00011

All QV gates have passed:
- S08: Lint (`make lint`) — PASS
- S09: Format (`make format`) — PASS
- S10: Typecheck (`make typecheck`) — PASS
- S11: Unit tests (`make test-unit`) — PASS (579 tests)
- S12: Integration tests (`make allure-integration`) — PASS (329 tests)
- S13: Unit tests (`make test-unit`) — PASS (579 tests)
- S14: Integration tests (`make allure-integration`) — PASS (329 tests)
