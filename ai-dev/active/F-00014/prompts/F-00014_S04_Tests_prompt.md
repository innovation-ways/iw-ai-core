# F-00014_S04_Tests_prompt

**Work Item**: F-00014 — Project-Level Documentation System — Polish (Phase 4)
**Step**: S04
**Agent**: Tests

---

## Input Files

- `ai-dev/active/F-00014/F-00014_Feature_Design.md` — Design document
- All S01–S03 implementation reports
- `tests/CLAUDE.md` — Read first
- `tests/conftest.py`

## Output Files

- `tests/integration/test_doc_polish.py` — All integration tests for Phase 4
- `ai-dev/work/F-00014/reports/F-00014_S04_Tests_report.md` — Step report

## Context

Integration tests for **F-00014: Documentation Polish**. Cover all 7 acceptance criteria and all boundary cases. Key complexity: link validation requires mocking HTTP (use `httpx`'s `MockTransport` or `respx` if available — check project deps), and ZIP export must be unpacked and inspected.

**CRITICAL**: NEVER connect to live DB. NEVER mock DB. Testcontainers only.

## Requirements

### 1. Diff Tests (`tests/integration/test_doc_polish.py`)

**`test_diff_route_shows_changes`**
- Create ProjectDoc, update content twice (2 versions)
- GET /api/project/{id}/docs/{doc_id}/diff?v1=1&v2=2
- Assert 200, HTML contains diff-line-added or diff-line-removed classes

**`test_diff_route_identical_versions`**
- Two versions with identical content
- Assert 200, HTML contains "identical" or "no differences"

**`test_diff_route_wrong_order_422`** — v1=2, v2=1 → assert 422  
**`test_diff_route_unknown_version_404`** — v1=99 → assert 404  

### 2. Export Tests

**`test_export_route_single_doc_zip`**
- Create ProjectDoc with content
- GET /api/project/{id}/docs/export?doc_ids={doc_id}
- Assert 200, Content-Type application/zip
- Unpack ZIP (io.BytesIO + zipfile), assert contains `{slug}.md`
- Assert ZIP content of .md matches doc.content

**`test_export_route_multi_doc_zip`**
- Create 2 ProjectDocs with content
- GET /api/project/{id}/docs/export?doc_ids={id1},{id2}
- Unpack ZIP, assert subdirectories for each doc

**`test_export_route_skips_no_content_doc`** — doc with content=None → ZIP excludes it  
**`test_export_cli_generates_files`** — CliRunner, assert files created in tmp_path  
**`test_export_cli_unknown_project_exits_1`** — exit code 1  

### 3. Link Validation Tests

**`test_validate_links_internal_not_found`**
- Create ProjectDoc with content: `[link](docs/missing.md)`
- GET /api/project/{id}/docs/{doc_id}/validate-links
- Assert 200, HTML contains "not_found"
- Assert doc.broken_links updated in DB

**`test_validate_links_all_valid`**
- Create real file in tmp repo path; reference it in content
- Assert response contains "All links valid"
- Assert doc.broken_links == []

**`test_validate_links_external_404`**
- Mock httpx to return 404 for external URL
- Assert broken links contains `{"type": "external", "status": "404"}`

**`test_validate_links_no_content_422`** — doc.content=None → 422  

### 4. Global Search Tests

**`test_global_search_page_200`** — GET /docs → 200  

**`test_global_search_returns_cross_project_results`**
- Register 2 projects, create docs in each with "authentication" in content
- GET /api/docs/search?q=authentication
- Assert 200, HTML contains docs from both projects

**`test_global_search_excludes_archived`**
- Create doc with status=archived containing search keyword
- Assert archived doc NOT in results (without explicit archived filter)

**`test_global_search_filter_by_doc_type`**
- Create module doc and api doc with same keyword
- GET /api/docs/search?q=keyword&doc_type=api
- Assert only api doc in results

**`test_global_search_snippet_highlighted`**
- Create doc with "authentication" in content
- GET /api/docs/search?q=authentication
- Assert HTML contains highlighted term (either `<mark>` or `<b>`)

**`test_global_search_empty_results`** — query with no matches → empty state HTML  
**`test_global_search_groups_by_project`** — multiple projects → each has section header  

### 5. Boundary Tests (from design doc)

- `test_diff_large_content_truncated` — 600-line content diff → response contains "Show all" or truncation note
- `test_diff_route_same_version_422` — v1=2, v2=2 (same version) → assert 422 (validates `version_old >= version_new` guard in `diff_versions()`)
- `test_diff_non_adjacent_versions` — create 3 version snapshots, request diff between v1 and v3 (skipping v2) → assert 200, diff reflects v1→v3 change directly (v2 has no effect on the output)
- `test_export_empty_doc_ids_exports_all` — no doc_ids param → all non-archived docs exported
- `test_validate_links_max_links_limit` — 25 links in content → only first 20 validated
- `test_validate_links_transient_5xx_not_flagged` — external URL returns 503 → NOT in broken_links (transient)
- `test_validate_links_ssrf_blocked` — content contains `[link](http://localhost:9900/internal)` → blocked_ssrf entry in broken_links, no HTTP request made
- `test_global_search_empty_query_returns_empty` — GET /api/docs/search?q= → 200, empty state HTML (no unbounded result dump)

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass
2. `make test-integration` — pass
3. `make quality` — pass

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "Tests",
  "work_item": "F-00014",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_doc_polish.py"
  ],
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
