# F-00011 S06 Tests — Step Report

## What Was Done

Created comprehensive test coverage for F-00011: Project-Level Documentation System.

## Files Changed

- `tests/integration/test_docs_routes.py` — 20 new dashboard route integration tests
- `tests/integration/test_doc_commands_integration.py` — 4 new CLI integration tests (including E2E)
- `tests/unit/test_doc_service.py` — NOT CREATED (PostgreSQL-specific features require testcontainer)

## Test Coverage

### Dashboard Route Tests (`test_docs_routes.py`)
All routes in `dashboard/routers/docs.py` are tested:

| Test | Route | Status |
|------|-------|--------|
| `test_docs_library_empty_state` | GET /project/{id}/docs | PASS |
| `test_docs_library_with_docs` | GET /project/{id}/docs | PASS |
| `test_docs_library_404_for_unknown_project` | GET /project/{id}/docs | PASS |
| `test_docs_library_filter_by_type` | GET /api/{id}/docs/search | PASS |
| `test_docs_library_filter_by_status` | GET /api/{id}/docs/search | PASS |
| `test_docs_library_fts_search` | GET /api/{id}/docs/search | PASS |
| `test_docs_library_filter_plus_search_combined` | GET /api/{id}/docs/search | PASS |
| `test_docs_detail_renders_content` | GET /project/{id}/docs/{id} | PASS |
| `test_docs_detail_no_content_placeholder` | GET /project/{id}/docs/{id} | PASS |
| `test_docs_detail_not_found` | GET /project/{id}/docs/{id} | PASS |
| `test_docs_detail_shows_metadata_sidebar` | GET /project/{id}/docs/{id} | PASS |
| `test_docs_version_drawer` | GET /api/{id}/docs/{id}/versions | PASS |
| `test_docs_version_drawer_empty` | GET /api/{id}/docs/{id}/versions | PASS |
| `test_docs_pdf_no_content` | GET /project/{id}/docs/{id}/pdf | PASS |
| `test_docs_pdf_not_found` | GET /project/{id}/docs/{id}/pdf | PASS |
| `test_docs_pdf_with_content` | GET /project/{id}/docs/{id}/pdf | PASS |
| `test_invariant_version_matches_snapshot_count` | Invariant test | PASS |
| `test_invariant_content_hash_skip` | Invariant test | PASS |
| `test_invariant_fts_stays_current` | Invariant test | PASS |
| `test_invariant_pdf_path_only_set_on_success` | Invariant test | PASS |

### CLI Integration Tests (`test_doc_commands_integration.py`)

| Test | Description | Status |
|------|-------------|--------|
| `test_doc_update_oversized_content_exits_2` | Content >= 10 MB rejected with exit code 2 | PASS |
| `test_e2e_cli_write_dashboard_read` | Full roundtrip CLI -> DB -> Dashboard | PASS |
| `test_doc_update_unknown_project_exit_code_1` | Unknown project exits 1 | PASS |
| `test_doc_update_unchanged_content_no_new_version` | Idempotency check | PASS |

## Test Results

```
tests/unit/: 579 passed
tests/integration/: 329 passed (including 24 new tests)
```

## Issues/Observations

1. **Unit test file for DocService not created**: DocService uses PostgreSQL-specific features (JSONB, FTS triggers) that SQLite doesn't support. The existing `tests/integration/test_doc_service.py` provides comprehensive coverage with a real PostgreSQL testcontainer.

2. **Pre-existing mypy errors**: The mypy errors reported are in `orch/cli/worktree_commands.py` and `dashboard/routers/worktrees.py` - files not modified by this step. These are pre-existing issues in the codebase.

## Notes

- All new tests use the PostgreSQL testcontainer via `tests/integration/conftest.py`
- Tests follow CLAUDE.md conventions: URL replacement for psycopg2, FTS SQL execution after create_all
- E2E test verifies full roundtrip: CLI doc-update -> GET /docs -> GET /docs/{id} -> GET /versions -> doc-update again -> GET versions
