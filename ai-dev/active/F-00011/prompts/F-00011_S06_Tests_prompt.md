# F-00011_S06_Tests_prompt

**Work Item**: F-00011 — Project-Level Documentation System — Foundation (Phase 1)
**Step**: S06
**Agent**: Tests

---

## Input Files

- `ai-dev/active/F-00011/F-00011_Feature_Design.md` — Design document (Acceptance Criteria + Boundary Behavior sections are your test specification)
- All implementation reports: `ai-dev/work/F-00011/reports/F-00011_S0{1,2,4,5}_*_report.md`
- All implementation files listed in those reports
- `tests/CLAUDE.md` — Test conventions (read first)
- `tests/conftest.py` — Existing fixtures

## Output Files

- `tests/integration/test_docs_routes.py` — Dashboard route integration tests
- `tests/integration/test_doc_commands_integration.py` — CLI integration tests (if not already covered by S04)
- `tests/unit/test_doc_service.py` — DocService unit tests (supplement S02 tests if needed)
- `ai-dev/work/F-00011/reports/F-00011_S06_Tests_report.md` — Step report

## Context

You are writing additional test coverage for **F-00011: Project-Level Documentation System**.

S01 (Database) and S02 (Backend) should already have unit tests for models and DocService. S04 (API/CLI) should have CLI tests. Your job is to add:

1. **Integration tests for dashboard routes** — all new HTTP endpoints
2. **Fill any gaps** in existing unit/CLI tests based on the design document's Acceptance Criteria and Boundary Behavior table
3. **End-to-end integration test** — full roundtrip from CLI write to dashboard read

Read `tests/CLAUDE.md` thoroughly before writing any test. Follow every convention there exactly: testcontainers setup, session fixtures, FTS SQL execution, URL construction.

**CRITICAL rules from CLAUDE.md:**
- NEVER connect to live DB (port 5433)
- NEVER mock the database in integration tests
- MUST replace psycopg2 URLs: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`
- MUST run `PROJECT_DOCS_FTS_FUNCTION_SQL` + `PROJECT_DOCS_FTS_TRIGGER_SQL` after `Base.metadata.create_all()`

## Requirements

### 1. Dashboard Route Integration Tests (`tests/integration/test_docs_routes.py`)

Test every route defined in `dashboard/routers/docs.py`. Use the existing test HTTP client pattern (check how other integration tests for dashboard routes are structured).

**Test: `test_docs_library_empty_state`**
```
Given: Project exists, no ProjectDoc records
When: GET /project/{project_id}/docs
Then: 200 response, HTML contains empty state indicator
```

**Test: `test_docs_library_with_docs`**
```
Given: Project with 3 ProjectDoc records (module, api, architecture types)
When: GET /project/{project_id}/docs
Then: 200 response, HTML contains all 3 doc titles
```

**Test: `test_docs_library_filter_by_type`**
```
Given: Project with 1 module doc and 1 api doc
When: GET /api/project/{id}/docs/search?doc_type=module
Then: 200 response, HTML contains module doc title, does NOT contain api doc title
```

**Test: `test_docs_library_fts_search`**
```
Given: ProjectDoc with content containing "authentication module"
When: GET /api/project/{id}/docs/search?q=authentication
Then: 200 response, HTML contains the doc title
When: GET /api/project/{id}/docs/search?q=nonexistent_xyz
Then: 200 response, HTML contains empty state
```

**Test: `test_docs_detail_renders_content`**
```
Given: ProjectDoc with markdown content "# Hello\n\nThis is a test doc."
When: GET /project/{project_id}/docs/{doc_id}
Then: 200 response, HTML contains rendered heading (not raw markdown)
And: HTML contains metadata sidebar with type, status, version
```

**Test: `test_docs_detail_no_content_placeholder`**
```
Given: ProjectDoc with content=None (planned doc)
When: GET /project/{project_id}/docs/{doc_id}
Then: 200 response, HTML contains "Content not yet generated" placeholder
```

**Test: `test_docs_detail_not_found`**
```
When: GET /project/{project_id}/docs/nonexistent-doc
Then: 404 response
```

**Test: `test_docs_version_drawer`**
```
Given: ProjectDoc updated 3 times (3 version snapshots)
When: GET /api/project/{id}/docs/{doc_id}/versions
Then: 200 response, HTML contains all 3 version numbers
```

**Test: `test_docs_pdf_download`**
```
Given: ProjectDoc with markdown content
When: GET /project/{project_id}/docs/{doc_id}/pdf
Then: Response with Content-Type: application/pdf OR 501 if WeasyPrint not installed
And: If 200, Content-Disposition header contains filename
```

**Test: `test_docs_pdf_no_content`**
```
Given: ProjectDoc with content=None
When: GET /project/{project_id}/docs/{doc_id}/pdf
Then: 404 response
```

### 2. End-to-End Integration Test

**Test: `test_e2e_cli_write_dashboard_read`**
```
Given: Project is registered
Step 1: Call iw doc-update via CliRunner with --title, --content, --doc-type, --tier, --status
Step 2: Assert CLI exits 0 and returns JSON with version=1
Step 3: GET /project/{id}/docs — assert doc title appears in response
Step 4: GET /project/{id}/docs/{doc_id} — assert content rendered
Step 5: GET /api/project/{id}/docs/{doc_id}/versions — assert 1 version entry
Step 6: Call iw doc-update again with different --content
Step 7: GET /api/project/{id}/docs/{doc_id}/versions — assert 2 version entries
```

### 3. Boundary Behavior Tests

Cover every row from the design document's "Boundary Behavior" table. For each:
- Name the test after the scenario
- Assert the exact expected behavior

Key boundary cases to add (if not already covered):
- `test_doc_update_unchanged_content_no_new_version` — idempotency
- `test_doc_update_unknown_project_exit_code_1` — error handling
- `test_docs_library_filter_plus_search_combined` — intersection filter
- `test_docs_pdf_cached_file_missing_regenerates` — stale PDF path handling
- `test_doc_update_oversized_content_exits_2` — content ≥ 10 MB → exit code 2 (generate a 10 MB+ string, assert CLI exits 2 without touching DB)

### 4. Invariant Tests

Write one test per invariant from the design document:

- `test_invariant_version_matches_snapshot_count` — after N updates, version == N version snapshots
- `test_invariant_content_hash_skip` — identical content → no new snapshot created
- `test_invariant_fts_stays_current` — insert doc, update content, assert FTS index contains new keyword
- `test_invariant_pdf_path_only_set_on_success` — if PDF generation fails, pdf_path remains None

## Project Conventions

Read `tests/CLAUDE.md` fully. Pay attention to:
- Fixture structure and how the testcontainer is set up
- How the HTTP test client is instantiated
- Where fixtures live (conftest.py vs local file)
- Naming conventions for test files and functions
- Whether to use `pytest.mark.integration` or similar markers

## Test Verification (NON-NEGOTIABLE)

After writing all tests:
1. `make test-unit` — all unit tests pass
2. `make test-integration` — all integration tests pass
3. `make quality` — ruff + mypy pass

Report the exact test counts (passed/failed/skipped) for both suites.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "Tests",
  "work_item": "F-00011",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_docs_routes.py",
    "tests/integration/test_doc_commands_integration.py",
    "tests/unit/test_doc_service.py"
  ],
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
