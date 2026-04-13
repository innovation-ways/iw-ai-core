# F-00012 S13 QvGate Report — Integration Tests

## What was done

Ran the full integration test suite via `make allure-integration` (`pytest tests/integration/ -v --alluredir=allure-results`).

## Test Results

**360 tests passed**, 3 warnings (SQLAlchemy session transaction warnings — non-critical, already present in prior runs).

No failures.

### Key test groups verified
- Doc generation job lifecycle (success, failure, stall detection, concurrent limit)
- CLI commands (`doc-job-start`, `doc-job-done`)
- API routes (generate, status poll, job history)
- SSE event stream coverage
- Full doc service CRUD + FTS
- Dashboard pages, fragments, actions
- Batch lifecycle, CLI, archive
- Fix cycle logic
- Models, migrations, search

## Files Changed

No source files changed — this step only runs verification.

## Issues / Observations

None. The integration test suite is clean.
