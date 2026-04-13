# F-00014 S13 QV Gate Report — Integration Tests

**Step**: S13  
**Gate**: integration-tests  
**Command**: `make allure-integration`  
**Result**: PASSED

## Summary

Integration tests gate passed — 408 tests collected and all passed in 16.42s.

## Quality Gates Status

| Gate | Step | Command | Result |
|------|------|---------|--------|
| Linting | S06 | `make lint` | PASSED |
| Formatting | S07 | `make format` | PASSED |
| Type checking | S08 | `make typecheck` | PASSED |
| Architecture | S09 | `make arch-check` | PASSED (no-op) |
| Security SAST | S10 | `make security-sast` | PASSED |
| Unit tests | S11 | `make test-unit` | PASSED |
| Frontend tests | S12 | `make test-frontend` | PASSED (no-op) |
| Integration tests | S13 | `make allure-integration` | PASSED |

## Files Changed

None — this is a verification gate; all 408 integration tests in `tests/integration/` passed.

## Test Results

- **408 passed**, 3 warnings in 16.42s
- Key test suites covered: doc polish (diff, export, link validation, global search), doc automation, doc generation, doc routes, batch lifecycle, dashboard pages/fragments, CLI commands, SSE events, models, FTS triggers
- 3 SAWarnings about transaction rollback on unique constraint conflict (test isolation artifact, not functional issues)

## Observations

- All F-00014 features (diff_versions, export_bundle, validate_links, global search) covered by integration tests in `test_doc_polish.py` and `test_doc_service.py`
- 3 warnings are cosmetic SQLAlchemy SAWarnings related to test isolation and do not affect functionality
- All quality gates for F-00014 are now complete