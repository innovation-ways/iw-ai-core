# F-00014_S02_API_prompt

**Work Item**: F-00014 — Project-Level Documentation System — Polish (Phase 4)
**Step**: S02
**Agent**: API

---

## Input Files

- `ai-dev/active/F-00014/F-00014_Feature_Design.md` — Design document
- `ai-dev/work/F-00014/reports/F-00014_S01_Backend_report.md` — S01 report
- `dashboard/routers/docs.py` — Existing docs router (extend)
- `dashboard/routers/search.py` — Existing search router (model global docs search on this)
- `CLAUDE.md`, `dashboard/CLAUDE.md`

## Output Files

- `dashboard/routers/docs.py` — Extended with diff, export, link validation routes
- `dashboard/routers/docs_global.py` — New global /docs search router
- `ai-dev/work/F-00014/reports/F-00014_S02_API_report.md` — Step report

## Context

You are implementing the API layer for **F-00014: Documentation Polish**. This step adds the version diff endpoint, ZIP export downloads, link validation trigger, and the global cross-project documentation search page and search API.

## Requirements

### 1. Version Diff Route

```
GET /api/project/{project_id}/docs/{doc_id}/diff?v1={n}&v2={m}
```

- Calls `DocService.diff_versions(project_id, doc_id, v1, v2)`
- Returns htmx fragment: `docs_diff.html` with the diff lines
- 404 if doc not found; 422 if v1 >= v2; 404 if version not found
- If diff is empty (identical content): return fragment showing "No differences found"

### 2. Export Bundle Route

```
GET /api/project/{project_id}/docs/export?doc_ids={comma-separated}
```

- Parses `doc_ids` query param (comma-separated list of doc `doc_id` values; if empty, export all)
- Calls `DocService.export_bundle()` passing `render_html_fn` and `render_pdf_fn` lambdas
- Returns `StreamingResponse` with `application/zip` and `Content-Disposition: attachment; filename="{project_id}-docs-export.zip"`
- 404 if project not found
- 422 if all requested doc_ids are unknown

### 3. Link Validation Route

```
GET /api/project/{project_id}/docs/{doc_id}/validate-links
```

- Calls `DocService.validate_links(doc, repo_root)` (runs in `asyncio.to_thread` to avoid blocking)
- Returns htmx fragment: `docs_broken_links.html` with results
- Updates `doc.broken_links` in DB via the service
- 404 if doc not found; 422 if doc has no content

### 4. Global Docs Search Page

Create `dashboard/routers/docs_global.py`:

```
GET /docs
```

- Full-page route (not a fragment)
- Template: `dashboard/templates/docs_global.html`
- Context: all projects list (for project filter dropdown), initial empty results

```
GET /api/docs/search?q={query}&doc_type={}&status={}&tier={}&project_id={}
```

- Calls `DocService.search_docs_global(search=q, ...)` 
- Returns htmx fragment: `docs_global_results.html`
- Results grouped by project: `{project_id: [{"doc": ProjectDoc, "snippet": str}, ...]}`
- 200 with empty state fragment if no results

Register the new router in the app factory with prefix `` (no prefix — `/docs` is top-level).

### 5. Single-Doc Export Route (for per-card export button)

```
GET /api/project/{project_id}/docs/{doc_id}/export
```

- Same as bulk export but for single doc
- ZIP filename: `{slug}-v{version}.zip`

## Project Conventions

- Read `dashboard/CLAUDE.md` before writing routes
- Match session injection, error handling, and response patterns of `docs.py`
- All `asyncio.to_thread` calls must be awaited properly (if dashboard uses async routes)
- `StreamingResponse` for ZIP: use `io.BytesIO` as the content stream

## Test Verification (NON-NEGOTIABLE)

1. `make quality` — pass

Note: Route integration tests are owned by S04 (tests-impl). Do not create test files in this step.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "API",
  "work_item": "F-00014",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/docs.py",
    "dashboard/routers/docs_global.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
