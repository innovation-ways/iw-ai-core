# F-00037_S02_Backend_report

## Step: S02 — Backend Implementation

**Work Item**: F-00037 — Doc-Type Guides — Editable Editorial Guidelines  
**Agent**: Backend  
**Completion Status**: complete

## Summary

The implementation for DocTypeGuide model and service layer was already in place when this step started. The work completed includes:

1. **Verified** `DocTypeGuide` model exists in `orch/db/models.py` (lines 971-986)
2. **Verified** `guide_snapshot` column exists in `DocGenerationJob` (lines 952-956)
3. **Verified** `get_type_guide()` and `save_type_guide()` methods exist in `DocService` (lines 808-820)
4. **Verified** `create_doc_job()` snapshots the guide via `guide_snapshot=self.get_type_guide(doc.doc_type.value)` (line 476)
5. **Created** unit tests in `tests/unit/test_doc_type_guide_service.py` (4 tests)
6. **Fixed** pre-existing test bug in `tests/unit/test_doc_job_poller.py::TestDocServiceJobLifecycle::test_create_doc_job` where the mock setup didn't properly mock `doc.doc_type.value`

## Files Changed

| File | Change |
|------|--------|
| `tests/unit/test_doc_type_guide_service.py` | Created — 4 unit tests for DocTypeGuide service methods |
| `tests/unit/test_doc_job_poller.py` | Fixed mock setup for `test_create_doc_job` to properly mock `doc.doc_type.value` |

## Test Results

```
658 passed, 1 warning in 1.44s (all unit tests)
```

New tests added (`tests/unit/test_doc_type_guide_service.py`):
- `test_get_type_guide_returns_none_when_missing` ✓
- `test_get_type_guide_returns_content_when_present` ✓
- `test_save_type_guide_inserts_new_row` ✓
- `test_save_type_guide_updates_existing_row` ✓

## Quality Checks

- **ruff**: All checks passed
- **mypy**: No issues found in `orch/db/models.py` or `orch/doc_service.py`

## Notes

- The implementation was already complete when step S02 started — this appears to be work from a previous session
- Fixed `test_create_doc_job` which had incomplete mock setup that didn't properly mock `doc.doc_type.value` (required for the `guide_snapshot` feature added in `create_doc_job`)
- The existing `DocService.get_type_guide()` implementation uses `session.get()` rather than `session.execute(select(...))` as specified in the requirements, but this is functionally equivalent and simpler
