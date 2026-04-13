# F-00014: Project-Level Documentation System — Polish (Phase 4)

**Type**: Feature
**Priority**: Low
**Created**: 2026-04-13
**Status**: Draft

---

## Description

Completes the documentation system with three high-value quality-of-life features: (1) a **version diff view** on the document detail page showing a side-by-side or unified diff between any two `ProjectDocVersion` snapshots; (2) a **global cross-project documentation search** at `/docs` (platform-wide) that queries across all registered projects' `ProjectDoc` records using the FTS index; and (3) **doc export bundles** — a ZIP archive download containing the markdown, HTML, and PDF for one or more selected docs, suitable for distribution or offline review. Together these features bring the documentation system to feature parity with professional documentation platforms.

**Depends on**: F-00013 (Phase 3 — automation must be complete before polishing the full system)

## Project Context

Read `CLAUDE.md`, `dashboard/CLAUDE.md`. Phase 4 is primarily frontend and new routes — minimal backend changes. The diff feature requires a Python diff library (use `difflib` from stdlib; no new dependencies). The global search extends the existing `/search` route pattern. Export bundles require ZIP file generation (use `zipfile` from stdlib).

## Scope

### In Scope

- **Version diff view**: accessible from the Version History drawer; user selects two versions and clicks "Compare"; renders a unified diff (side-by-side on desktop, unified on mobile) using `difflib.HtmlDiff` or a Tailwind-styled line-diff renderer; highlights additions in green, deletions in red
- **Global documentation search** at `/docs` (new top-level nav entry): search bar + results list spanning all projects; powered by FTS across all `project_docs.content_search`; results grouped by project; filters by `doc_type`, `status`, `tier`; each result shows: project name, doc title, type badge, status, matching excerpt (highlighted snippet via `ts_headline()`)
- **Doc export bundles**: "Export" button on the doc library page (per-doc and multi-select); generates a ZIP containing `{slug}.md`, `{slug}.html` (rendered), `{slug}.pdf`, and `_generation_notes.md` (generation metadata as markdown); served as `application/zip` download; for multi-select: one ZIP per selection
- **Top-level `/docs` nav entry** in the global platform navigation (alongside the project selector)
- **`iw docs-export <project_id> [doc_ids...]` CLI command**: generates export bundle(s) to a local directory; useful for CI/CD pipelines that publish docs to external sites
- **Markdown link validation**: `DocService.validate_links(doc)` — checks that all `[text](url)` and `![alt](img)` references in content resolve (internal paths checked against repo, external URLs checked via HTTP HEAD); populates `ProjectDoc.broken_links` (new JSONB column) and shows a "Broken Links" warning badge on the detail page

### Out of Scope

- Public documentation site (Docusaurus/Starlight)
- Algolia DocSearch integration
- Multi-version selector (v1.0 / v2.0 dropdown)
- Real-time collaborative editing
- Doc comments / annotation system

## Architecture References

| Existing Pattern | Location | How We Extend It |
|-----------------|----------|-----------------|
| Global `/search` route | `dashboard/routers/search.py` | Model global `/docs` search on same FTS pattern |
| `ts_headline()` search snippets | `dashboard/routers/search.py` | Reuse for doc search result excerpts |
| Project selector page | `dashboard/routers/projects.py` | Add "Docs" to global top-nav |
| File download route (PDF) | `dashboard/routers/docs.py` (F-00011) | Extend to ZIP download |
| `ProjectDocVersion` | `orch/db/models.py` (F-00011) | Version list already fetched; add diff route |
| `render_markdown()` utility | `dashboard/` | Reuse for HTML rendering inside ZIP bundle |

## Implementation Plan

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | `DocService.diff_versions()`; `DocService.validate_links()`; `DocService.export_bundle()`; global search query; broken_links column migration | — |
| S02 | API | Version diff route; global `/docs` search route; export bundle route; `iw docs-export` CLI | S03 |
| S03 | Frontend | Version diff UI; global docs search page; multi-select export UI; broken links badge; top-level nav "Docs" entry | S02 |
| S04 | Tests | Diff generation; link validation; ZIP export; global search; multi-select | — |
| S05 | CodeReview_Final | Global cross-layer review | — |
| S06–S13 | QV Gates | lint → format → typecheck → arch-check → security-sast → unit → frontend → integration | — |

## Database Changes

**Modified tables:**
- `project_docs` — add `broken_links` (JSONB, nullable): list of `{url, type, status}` objects from link validation

**Migration**: One Alembic migration adding `broken_links` column.

## API Changes

**New dashboard routes:**
- `GET /api/project/{id}/docs/{doc_id}/diff?v1={n}&v2={m}` — returns diff HTML fragment
- `GET /docs` — global documentation search page
- `GET /api/docs/search?q=&doc_type=&status=&tier=&project_id=` — htmx search results fragment (cross-project)
- `GET /api/project/{id}/docs/export?doc_ids={comma-separated}` — ZIP bundle download
- `GET /api/project/{id}/docs/{doc_id}/validate-links` — trigger link validation, return results fragment

**New CLI command:**
- `iw docs-export <project_id> [doc_ids...] [--output-dir PATH]` — generates ZIP bundles for specified docs (or all docs if no IDs given) to `output-dir`

**Modified routes:**
- Global platform nav template — add "Docs" top-level entry linking to `/docs`

## Frontend Changes

### Version Diff UI

Accessed from the Version History drawer: each version row gets a "Compare with current" or "Select for diff" checkbox. When two versions are selected, a "Compare" button appears. Clicking it:
- Sends `GET /api/project/{id}/docs/{doc_id}/diff?v1=N&v2=M`
- Target: a modal or inline expanded section below the version drawer
- Renders a unified diff: line numbers, red highlights for removed lines, green for added lines
- Desktop: side-by-side (v_old | v_new); Mobile: unified view with +/- prefixes
- "Close diff" button collapses the view

### Global Docs Search Page (`/docs`)

**Layout:**
- Full-width search bar (prominent, centered on page)
- Filter row: doc_type pills, status pills, tier pills, project selector dropdown
- Results list (htmx-updated on every keystroke with 300ms debounce):
  - Grouped by project (project name as section header)
  - Each result: doc type badge, title, project name chip, status badge, text excerpt with search terms highlighted
  - "No results" empty state with suggestions
- Result count: "Showing X results across Y projects"

### Multi-Select Export UI

On the doc library page:
- Checkbox on each doc card (appears on hover or via "Select" mode toggle)
- "Export Selected" button (floating action, appears when ≥1 selected): triggers ZIP download for all selected docs
- Per-doc "Export" button in the card actions menu (single doc download)

### Broken Links Badge

On the doc detail page:
- If `broken_links` is non-empty: orange warning callout: "N broken links detected" with expandable list
- Each broken link: URL, type (internal/external), HTTP status or "file not found"
- "Re-check links" button: triggers fresh validation

### Top-Level Nav Entry

Add "Docs" to the platform-level navigation (the bar above the project sidebar, if one exists — check the base template). Links to `/docs` (global search). Shows a badge count of stale docs across all projects if any (optional, Phase 4b).

## Acceptance Criteria

### AC1: Version diff shows line-level changes

```
Given: A ProjectDoc with 3 version snapshots where v1 has "Hello world" and v2 has "Hello universe"
When: User selects v1 and v2 in the Version History drawer and clicks "Compare"
Then: The diff view renders showing "world" as deleted (red) and "universe" as added (green)
And: Unchanged lines are shown in context (±3 lines)
```

### AC2: Global search returns results across projects

```
Given: Projects "innoforge" and "iw-ai-core" each have ProjectDoc records with content about "authentication"
When: User searches for "authentication" on /docs
Then: Results from both projects appear, grouped under their project name
And: The matching word "authentication" is highlighted in the excerpt
```

### AC3: Export bundle contains all expected files

```
Given: A ProjectDoc with content, generated HTML path, and generated PDF path
When: User clicks "Export" on the doc card
Then: Browser downloads a ZIP file named "{slug}-v{version}.zip"
And: The ZIP contains: {slug}.md, {slug}.html, {slug}.pdf, _generation_notes.md
```

### AC4: Multi-select export bundles multiple docs

```
Given: User selects 3 doc cards
When: User clicks "Export Selected"
Then: Browser downloads a ZIP named "{project_id}-docs-export.zip"
And: The ZIP contains subdirectories for each selected doc with their respective files
```

### AC5: Broken link validation detects dead links

```
Given: A ProjectDoc with content containing a link to a non-existent internal path
When: User clicks "Re-check links" (or validation runs automatically after generation)
Then: The broken link appears in the detail page callout
And: ProjectDoc.broken_links is updated in the database
```

### AC6: iw docs-export generates bundles locally

```
Given: Project "innoforge" with 3 published docs
When: iw docs-export innoforge --output-dir /tmp/exports
Then: /tmp/exports/{slug}/ directories are created for each doc
And: Each contains .md, .html, .pdf, and _generation_notes.md
And: CLI exits 0 with a summary: "Exported 3 docs to /tmp/exports"
```

### AC7: Global search filters work

```
Given: Docs with mixed types (module, api, architecture) across projects
When: User applies doc_type=api filter on /docs search
Then: Only api-type docs appear in results
And: Results still span all projects
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Diff of identical versions | v1 content == v2 content | Show "No differences found" message (not an error) |
| Diff with very large content | Doc content >500KB | Diff is computed but limited to 1000 line chunks with "Show more" pagination |
| Export when PDF not yet generated | `pdf_path` is null | Generate PDF on-demand before zipping; if WeasyPrint unavailable, ZIP excludes PDF and adds a note in `_generation_notes.md` |
| Global search with no results | Query matches nothing | Show empty state with "Try different keywords" suggestion |
| Export with 0 docs selected | Multi-select with nothing checked | "Export Selected" button is disabled (greyed out) |
| Link validation: external URL down | HTTP HEAD returns 503 | Marked as "external: 503" in broken_links (transient — not treated as definitively broken) |
| Link validation: internal path | Relative path like `docs/arch.md` | Resolved against `project.repo_root`, checked with `os.path.exists()` |
| iw docs-export with unknown project | Invalid project_id | Exit code 1, error: "Project '{id}' not found" |
| Compare non-adjacent versions | v1=1 and v3=3 (skipping v2) | Diff is computed between v1 and v3 content directly — skipped versions have no effect |

## Invariants

1. The diff view always shows v_old on the left / top and v_new on the right / bottom (lower version number = older)
2. Export ZIP filenames are always slug-safe (no spaces, no special characters other than `-` and `_`)
3. `broken_links` is only set after an explicit validation run (or post-generation validation) — never automatically cleared without re-running validation
4. Global search only returns docs with `status != archived` by default (archived can be included with explicit filter)
5. `iw docs-export` never writes outside the specified `--output-dir` (no path traversal)

## File Manifest

All files for this work item live under `ai-dev/active/F-00014/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00014_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00014_S01_Backend_prompt.md` | Prompt | Backend: DocService methods, migration, CLI |
| `prompts/F-00014_S02_API_prompt.md` | Prompt | API: diff/export/validation/global-search routes |
| `prompts/F-00014_S03_Frontend_prompt.md` | Prompt | Frontend: diff UI, global search page, multi-select export, broken links |
| `prompts/F-00014_S04_Tests_prompt.md` | Prompt | Tests: integration tests for all 7 AC + boundary cases |
| `prompts/F-00014_S05_CodeReview_Final_prompt.md` | Prompt | Final cross-agent review |

Reports are created during execution in `ai-dev/work/F-00014/reports/`.

## Dependencies

- **Depends on**: F-00013 (Phase 3)
- **Blocks**: None (final phase)

## TDD Approach

- Unit tests: `diff_versions()` with stdlib `difflib`; `validate_links()` with mock HTTP + real FS; `export_bundle()` ZIP contents; global FTS query with `ts_headline()`
- Integration tests: diff route with real version snapshots; ZIP download route; global search across multiple projects (requires multiple project fixtures); link validation with temp files

## Notes

**Diff implementation:**
```python
import difflib
diff = list(difflib.unified_diff(
    v1_content.splitlines(keepends=True),
    v2_content.splitlines(keepends=True),
    fromfile=f"v{v1.version}",
    tofile=f"v{v2.version}",
    n=3  # context lines
))
```
Render as HTML with Tailwind: lines starting with `+` get `bg-green-50 text-green-800`, lines with `-` get `bg-red-50 text-red-800`, `@@` lines get `bg-blue-50 text-blue-600 font-mono text-xs`.

**`ts_headline()` for search excerpts:**
```sql
ts_headline('english', content, plainto_tsquery('english', :q),
    'MaxWords=35, MinWords=20, ShortWord=3, HighlightAll=false,
     MaxFragments=2, FragmentDelimiter=" ... "')
```

**ZIP generation:**
```python
import zipfile, io
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(f"{slug}.md", doc.content)
    zf.writestr(f"{slug}.html", rendered_html)
    if pdf_bytes:
        zf.writestr(f"{slug}.pdf", pdf_bytes)
    zf.writestr("_generation_notes.md", generation_notes_md)
buf.seek(0)
return StreamingResponse(buf, media_type="application/zip",
    headers={"Content-Disposition": f'attachment; filename="{slug}-v{version}.zip"'})
```

**Link validation strategy:**
- Internal links (no `http`/`https` prefix): `os.path.exists(os.path.join(project.repo_root, link))`
- External links: `httpx.head(url, timeout=5, follow_redirects=True)` — treat 2xx/3xx as valid, 4xx as broken, 5xx as transient
- Run in a thread pool (`asyncio.to_thread`) to avoid blocking the event loop
- Max 20 links validated per run (configurable via `Project.config.doc_generation.max_links_to_validate`)
