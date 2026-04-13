# F-00013 S12 QV Gate Report — Integration Tests

## What Was Done

Executed the QV gate step S12 (`make allure-integration`) for work item F-00013: Project-Level Documentation System — Automation (Phase 3).

## Command

```bash
make allure-integration
# → uv run pytest tests/integration/ -v --alluredir=allure-results
```

## Test Results

- **Status**: PASSED
- **Total tests**: 380
- **Passed**: 380
- **Failed**: 0
- **Warnings**: 3 (non-fatal SAWarnings for transaction rollback edge cases, pre-existing)
- **Duration**: 14.45s

## Files Changed

None — this is a read-only QV gate step.

## Observations

All 380 integration tests pass, including the F-00013 feature tests covering:
- `test_doc_automation.py` (merge hook, staleness detection, lint gate, config panel)
- `test_doc_commands_integration.py` (CLI doc update e2e)
- `test_doc_generation.py` (job lifecycle, concurrent limit, skill selection)
- `test_doc_job_routes.py` (job routes)
- `test_doc_service.py` (doc service layer)
- `test_docs_routes.py` (dashboard routes and invariants)
- `test_project_docs.py` (DB model layer)

The 3 warnings are pre-existing and unrelated to F-00013.

## Summary

S12 is the final QV gate. All quality gates (S05–S12) have now passed:
- S05: lint ✓
- S06: format ✓
- S07: typecheck ✓
- S08: arch-check ✓
- S09: security-sast ✓
- S10: unit-tests ✓
- S11: frontend-tests ✓
- S12: integration-tests ✓

The F-00013 feature is complete and ready for release.