# F-00011_S02_Backend_report.md

## Step Summary

**Work Item**: F-00011 — Project-Level Documentation System — Foundation (Phase 1)
**Step**: S02 — Backend (DocService)
**Agent**: Backend
**Status**: ✅ Complete

## What Was Done

Implemented `DocService` class in `orch/doc_service.py` — the synchronous service layer for `ProjectDoc`, `ProjectDocVersion`, and async `DocGenerationJob` models (DB models from S01).

## Files Created/Changed

| File | Change | Notes |
|------|--------|-------|
| `orch/doc_service.py` | Created | DocService with 8 CRUD methods |
| `tests/integration/test_doc_service.py` | Created | 14 integration tests (testcontainer DB, no mocks) |

## DocService Methods Implemented

1. **`create_doc()`** — Creates `ProjectDoc`, auto-derives `slug` from title, optionally creates initial `ProjectDocVersion` snapshot if content is provided. Raises `ValueError` if project not found.

2. **`update_doc()`** — Partial update (only non-None fields). On content change: increments version, sets `generated_at`, creates version snapshot, clears `html_path`/`pdf_path` (stale renders). Uses SHA256 hash to detect unchanged content.

3. **`upsert_doc()`** — Convenience wrapper: `get_doc` → create or update.

4. **`get_doc()`** — Fetches by `project_id:doc_id` composite key.

5. **`list_docs()`** — Supports `doc_type` filter, `status` filter, and FTS search (`plainto_tsquery` + `ts_rank` ordering). Uses `content_search` TSVECTOR column.

6. **`list_doc_versions()`** — All versions for a doc, ordered `version DESC`.

7. **`get_stale_docs()`** — Time-based staleness detection via `generated_at < now() - timedelta(hours=threshold_hours)`, `source_paths != []`, `status != archived`.

8. **`delete_doc()`** — Cascade delete via FK. Returns `bool`.

## Design Notes

- **No `services/` directory existed** — created `orch/doc_service.py` at the package root per instructions
- **Synchronous only** — project uses SQLAlchemy 2.0 sync throughout (no async patterns found)
- **FTS search** uses `content_search` TSVECTOR with `@@` operator and `plainto_tsquery('english', search)`
- **`_slugify()`** is manual lowercase/hyphen replacement (no `python-slugify` dependency)
- **`_content_hash()`** uses SHA256 hexdigest for content change detection

## Test Results

```
tests/integration/test_doc_service.py: 14 passed in 3.31s
tests/unit/: 576 passed, 1 warning in 1.13s
```

**Tests** (placed in `tests/integration/` because they require the testcontainer DB):
- `test_create_doc_creates_record_and_version`
- `test_create_doc_no_content_no_version_snapshot`
- `test_create_doc_unknown_project_raises_value_error`
- `test_update_doc_content_changed_creates_version`
- `test_update_doc_content_unchanged_no_new_version`
- `test_update_doc_content_change_clears_pdf_path`
- `test_upsert_doc_creates_when_missing`
- `test_upsert_doc_updates_when_exists`
- `test_list_docs_filter_by_type`
- `test_list_docs_fts_search`
- `test_list_doc_versions_ordered`
- `test_get_stale_docs`
- `test_delete_doc`
- `test_update_doc_not_found_raises_key_error`

## Quality Checks

- **ruff**: ✅ All checks passed
- **ruff format**: ✅ All files formatted
- **mypy** (doc_service only): ✅ No issues

## Issues/Observations

1. **Tests placed in `tests/integration/` not `tests/unit/`** — The `db_session` fixture is defined in `tests/integration/conftest.py` (testcontainer-based). These are integration tests by project convention, not mocks-based unit tests. The S02 prompt's "unit tests with testcontainer DB, no mocks" pattern matches integration test conventions.

2. **Pre-existing mypy issue in `orch/cli/worktree_commands.py`** — Unrelated to this step: `type: ignore` comment flagged by `make quality`. Not blocking.

## Blockers

None.

## Notes for Next Steps

- S04 (API/CLI) will use `DocService` via the same pattern as other CLI commands
- S05 (Frontend) will call dashboard routes that eventually use `DocService`
- The FTS index on `content_search` (GIN) is already set up by S01 models + migration