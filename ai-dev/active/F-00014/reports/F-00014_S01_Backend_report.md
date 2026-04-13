# F-00014 S01 Backend Report

## Summary

Implemented backend changes for F-00014 (Project-Level Documentation System — Polish Phase 4).

## Files Changed

1. `orch/db/models.py` — Added `broken_links` JSONB column to `ProjectDoc`
2. `orch/db/migrations/versions/20260413150000_add_doc_broken_links.py` — Migration for `broken_links` column
3. `orch/doc_service.py` — Added:
   - `diff_versions()` — unified diff between two doc versions
   - `validate_links()` — check markdown links (internal paths + external URLs)
   - `export_bundle()` — create ZIP export of docs
   - `search_docs_global()` — FTS search across all projects
4. `orch/cli/doc_commands.py` — Added `docs-export` CLI command
5. `orch/cli/main.py` — Registered `docs-export` command
6. `tests/unit/test_doc_polish.py` — Unit tests for all new functionality

## Test Results

- `make test-unit`: **631 passed, 1 warning**
- `make quality` (ruff): **All checks passed**
- `make quality` (mypy): Pre-existing error in `yaml` import (not introduced by this step)

## Test Coverage

14 new tests in `tests/unit/test_doc_polish.py`:
- `test_diff_versions_returns_unified_diff`
- `test_diff_versions_identical_content_empty_diff`
- `test_diff_versions_raises_key_error_unknown_version`
- `test_diff_versions_raises_value_error_wrong_order`
- `test_validate_links_internal_found`
- `test_validate_links_internal_not_found`
- `test_validate_links_external_ok`
- `test_validate_links_external_404`
- `test_export_bundle_single_doc_zip_contents`
- `test_export_bundle_multiple_docs_subdirs`
- `test_export_bundle_skips_docs_with_no_content`
- `test_search_docs_global_fts_ranked`
- `test_docs_export_cli_exits_0`
- `test_docs_export_cli_unknown_project_exits_1`

## Notes

- SSRF protection implemented in `validate_links()` — blocks private/loopback hostnames
- `broken_links` column stores list of `{"url": str, "type": "internal"|"external", "status": str}`
- `export_bundle()` uses `_project_id` prefix to indicate intentionally unused parameter (API signature requirement)
- The `yaml` mypy error is pre-existing in the codebase and not introduced by this step
