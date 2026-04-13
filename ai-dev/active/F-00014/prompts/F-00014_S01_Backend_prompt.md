# F-00014_S01_Backend_prompt

**Work Item**: F-00014 — Project-Level Documentation System — Polish (Phase 4)
**Step**: S01
**Agent**: Backend

---

## Input Files

- `ai-dev/active/F-00014/F-00014_Feature_Design.md` — Design document (read fully)
- `orch/doc_service.py` — DocService (extend)
- `orch/db/models.py` — All models (add broken_links column)
- `CLAUDE.md`, `orch/CLAUDE.md`

## Output Files

- `orch/db/migrations/versions/{timestamp}_add_doc_broken_links.py` — Migration
- `orch/db/models.py` — Add `broken_links` column to `ProjectDoc`
- `orch/doc_service.py` — Add: `diff_versions()`, `validate_links()`, `export_bundle()`; extend global search
- `orch/cli/doc_commands.py` — Add `iw docs-export` command
- `ai-dev/work/F-00014/reports/F-00014_S01_Backend_report.md` — Step report

## Context

You are implementing the backend for **F-00014: Documentation Polish**. Three new capabilities: version diffs, link validation, and ZIP export bundles. All use Python stdlib — no new dependencies except `httpx` for external link checking (already likely in the project; verify before adding).

## Requirements

### 1. Migration: `broken_links` Column

Add `broken_links JSONB nullable` to `project_docs`. Each element: `{"url": str, "type": "internal"|"external", "status": str}`.

### 2. DocService: `diff_versions()`

```python
def diff_versions(
    self,
    project_id: str,
    doc_id: str,
    version_old: int,
    version_new: int,
) -> list[str]
```

- Fetches `ProjectDocVersion` records for the two version numbers
- Raises `KeyError` if either version not found
- Raises `ValueError` if `version_old >= version_new`
- Returns unified diff lines using `difflib.unified_diff()`:
  ```python
  import difflib
  lines = list(difflib.unified_diff(
      old_content.splitlines(keepends=True),
      new_content.splitlines(keepends=True),
      fromfile=f"v{version_old}",
      tofile=f"v{version_new}",
      n=3,
  ))
  return lines
  ```

### 3. DocService: `validate_links()`

```python
def validate_links(
    self,
    doc: ProjectDoc,
    repo_root: str,
    max_links: int = 20,
) -> list[dict]
```

- Parses all markdown links from `doc.content` using regex:
  ```python
  import re
  pattern = re.compile(r'!?\[([^\]]*)\]\(([^)]+)\)')
  links = [(m.group(1), m.group(2)) for m in pattern.finditer(doc.content or "")]
  ```
- Checks first `max_links` links only
- **SSRF protection**: before making any HTTP request, reject URLs that resolve to private/loopback addresses. Block URLs whose hostname is `localhost`, `127.*`, `10.*`, `172.16–31.*`, `192.168.*`, `::1`, or any `.local` / `.internal` suffix. Return `{"url": url, "type": "external", "status": "blocked_ssrf"}` for these — do NOT make the request.
- For each link URL:
  - If starts with `http://` or `https://`: apply SSRF check first, then `httpx.head(url, timeout=5, follow_redirects=True)`
    - 2xx/3xx → `{"url": url, "type": "external", "status": "ok"}`
    - 4xx → `{"url": url, "type": "external", "status": str(status_code)}`
    - 5xx → `{"url": url, "type": "external", "status": "transient_" + str(status_code)}`
    - Exception → `{"url": url, "type": "external", "status": "error"}`
  - Otherwise: resolve relative to `repo_root`, `os.path.exists(path)`:
    - Exists → `{"url": url, "type": "internal", "status": "ok"}`
    - Not exists → `{"url": url, "type": "internal", "status": "not_found"}`
- Returns only broken links (status != "ok" and not "transient_*"; blocked_ssrf IS returned as a broken link)
- Updates `doc.broken_links` in DB and commits

### 4. DocService: `export_bundle()`

```python
def export_bundle(
    self,
    project_id: str,
    doc_ids: list[str],
    render_html_fn: Callable[[str, ProjectDoc], str],
    render_pdf_fn: Callable[[str], bytes | None],
) -> bytes
```

- For each doc in `doc_ids`:
  - Read `doc.content` (skip if None)
  - Call `render_html_fn(doc.content, doc)` to get HTML string
  - Call `render_pdf_fn(html)` to get PDF bytes (may return None if WeasyPrint unavailable)
  - Generate `_generation_notes.md`: document metadata as markdown table
- Build ZIP in memory (`io.BytesIO` + `zipfile.ZipFile`):
  - Single doc: files at top level (`{slug}.md`, `{slug}.html`, `{slug}.pdf`, `_generation_notes.md`)
  - Multiple docs: subdirectory per doc (`{slug}/{slug}.md`, etc.)
- Returns ZIP bytes

### 5. Global Search Query in DocService

```python
def search_docs_global(
    self,
    search: str,
    doc_type: DocType | None = None,
    status: DocStatus | None = None,
    tier: DocTier | None = None,
    project_id: str | None = None,
    limit: int = 50,
) -> list[tuple[ProjectDoc, str]]
```

- **Guard**: if `search` is empty or whitespace-only, return `[]` immediately (do not execute the FTS query — an empty `plainto_tsquery` matches all rows, which is unbounded)
- Joins `project_docs` with `projects`
- FTS filter: `content_search @@ plainto_tsquery('english', :search)`
- `ts_headline()` for excerpt:
  ```sql
  ts_headline('english', content, plainto_tsquery('english', :search),
      'MaxWords=35, MinWords=20, ShortWord=3, MaxFragments=2,
       FragmentDelimiter=" ... "')
  ```
- Excludes archived docs by default (unless `status` filter explicitly includes archived)
- Returns `(ProjectDoc, headline_snippet)` tuples ordered by `ts_rank DESC`

### 6. CLI: `iw docs-export`

Add to `orch/cli/doc_commands.py`:

```
iw docs-export PROJECT_ID [DOC_IDS...] [--output-dir PATH]
```

- If no `DOC_IDS` given: export all non-archived docs in the project
- Generates ZIP bundle via `DocService.export_bundle()`
- Writes to `{output_dir}/{project_id}-docs-export.zip` (or individual `{slug}.zip` per doc)
- Validates output_dir for path traversal: must be an absolute path and must exist
- Exits 0 with summary; exits 1 on project not found; exits 2 on validation error

## TDD Requirement

Tests in `tests/unit/test_doc_polish.py`:
- `test_diff_versions_returns_unified_diff`
- `test_diff_versions_identical_content_empty_diff`
- `test_diff_versions_raises_key_error_unknown_version`
- `test_diff_versions_raises_value_error_wrong_order`
- `test_validate_links_internal_found`
- `test_validate_links_internal_not_found`
- `test_validate_links_external_ok` — mock httpx
- `test_validate_links_external_404` — mock httpx
- `test_export_bundle_single_doc_zip_contents`
- `test_export_bundle_multiple_docs_subdirs`
- `test_export_bundle_skips_docs_with_no_content`
- `test_search_docs_global_fts_ranked`
- `test_docs_export_cli_exits_0`
- `test_docs_export_cli_unknown_project_exits_1`

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass
2. `make quality` — pass

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "F-00014",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/{ts}_add_doc_broken_links.py",
    "orch/doc_service.py",
    "orch/cli/doc_commands.py",
    "tests/unit/test_doc_polish.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
