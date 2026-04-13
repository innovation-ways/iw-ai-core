# F-00011_S05_Frontend_prompt

**Work Item**: F-00011 — Project-Level Documentation System — Foundation (Phase 1)
**Step**: S05
**Agent**: Frontend

---

## Input Files

- `ai-dev/active/F-00011/F-00011_Feature_Design.md` — Design document (read the "UI Design" section fully)
- `ai-dev/work/F-00011/reports/F-00011_S01_Database_report.md` — S01 (models)
- `ai-dev/work/F-00011/reports/F-00011_S02_Backend_report.md` — S02 (DocService)
- `dashboard/CLAUDE.md` — Dashboard conventions (read before writing any template)
- `dashboard/routers/project_pages.py` — Existing project page routes to extend
- `dashboard/templates/` — Existing templates for style reference
- `dashboard/templates/fragments/nav_projects.html` — Sidebar nav to extend

## Output Files

- `dashboard/routers/docs.py` — New docs router
- `dashboard/templates/docs_library.html` — Doc library page template
- `dashboard/templates/docs_detail.html` — Document detail page template
- `dashboard/templates/fragments/docs_card.html` — Doc card fragment (htmx target)
- `dashboard/templates/fragments/docs_search_results.html` — htmx search results fragment
- `dashboard/templates/fragments/docs_version_drawer.html` — Version history drawer fragment
- `dashboard/templates/fragments/nav_projects.html` — Modified to add Docs nav entry
- `dashboard/routers/__init__.py` or app factory — Register new docs router
- `ai-dev/work/F-00011/reports/F-00011_S05_Frontend_report.md` — Step report

## Context

You are implementing the frontend UI for **F-00011: Project-Level Documentation System**.

This step must produce an **elegant, modern, polished** documentation interface. Study the existing dashboard templates carefully before writing a single line. Use the same Tailwind CSS utility classes, htmx patterns, color palette, and component patterns already established. The goal is a UI that feels native to the dashboard — not bolted on.

Read `dashboard/CLAUDE.md` thoroughly. Look at how `project_pages.py` structures routes and how templates use htmx for fragment updates. The design document's "UI Design" section is authoritative — implement it exactly.

## Requirements

### 1. Sidebar Navigation (8th Tab)

Modify `dashboard/templates/fragments/nav_projects.html` to add "Docs" as the 8th sidebar entry:

- Icon: document or book icon (use the same icon library already in use — check existing nav items)
- Label: "Docs"
- href: `/project/{project_id}/docs`
- Active state: same class pattern as existing active nav items
- Position: after "Analytics" (the current last item)

### 2. Docs Router (`dashboard/routers/docs.py`)

Create a FastAPI router with these routes:

```python
GET /project/{project_id}/docs
    → renders docs_library.html
    → context: project, docs=DocService.list_docs(project_id), doc_types, statuses

GET /project/{project_id}/docs/{doc_id}
    → renders docs_detail.html
    → context: project, doc=DocService.get_doc(project_id, doc_id), versions=DocService.list_doc_versions(...)
    → 404 if doc not found

GET /project/{project_id}/docs/{doc_id}/pdf
    → generates PDF and serves as file download
    → see PDF section below

GET /api/project/{project_id}/docs/search
    → htmx endpoint: query param `q` (search string), `doc_type` (filter), `status` (filter)
    → returns docs_search_results.html fragment
    → calls DocService.list_docs(project_id, search=q, doc_type=..., status=...)

GET /api/project/{project_id}/docs/{doc_id}/versions
    → htmx endpoint: returns docs_version_drawer.html fragment
    → calls DocService.list_doc_versions(project_id, doc_id)
```

Import and use `DocService` from the backend layer. Follow the session management pattern of existing routers exactly.

Register this router in the app factory with the same prefix/tag pattern as other routers.

### 3. Doc Library Page (`docs_library.html`)

**Layout requirements** (match existing dashboard page structure exactly):
- Page uses the same base template as other project pages
- Page header: "Documentation" h1 + optional subtitle "Project knowledge base, auto-generated and human-authored docs."

**Filter bar (above the card grid):**
- Doc type filter: pill buttons (`All`, `Module`, `API`, `Architecture`, `Release Notes`, `Error Catalog`, `Webhook Ref`, `User Guide`)
  - Active pill: filled background (primary color), inactive: bordered
  - Clicking a pill triggers htmx GET to `/api/project/{id}/docs/search` with `doc_type=` param
  - Target: `#docs-grid` (replaces card grid content)
- Status filter: pill buttons (`All`, `Draft`, `Published`, `Planned`, `Archived`) — same pattern
- Search input: text input with magnifier icon, `hx-get` on `input` event with 300ms debounce (`hx-trigger="input changed delay:300ms"`), target `#docs-grid`

**Card grid:**
- `id="docs-grid"` — htmx replaces this content on filter/search
- 3 columns on desktop (`grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6`)
- Each card: see `docs_card.html` requirements
- Empty state (when grid is empty): center-aligned, icon, "No documentation found" heading, descriptive subtext ("Use `iw doc-update` to add your first document."), monospace code example

### 4. Doc Card Fragment (`docs_card.html`)

Each card must feel like a well-designed documentation index card:

```
┌─────────────────────────────────────────┐
│ [Type Badge]  [Tier Badge]    [Status]  │
│                                         │
│  Title (text-lg font-semibold)          │
│  Editorial category (text-sm text-gray) │
│                                         │
│  v{version}  ·  {relative time}         │
│  {source count} sources                 │
│                                         │
│                    [View →] button      │
└─────────────────────────────────────────┘
```

**Badge colors** (Tailwind classes):
- `module`: `bg-purple-100 text-purple-700`
- `api`: `bg-blue-100 text-blue-700`
- `architecture`: `bg-indigo-100 text-indigo-700`
- `release_notes`: `bg-orange-100 text-orange-700`
- `error_catalog`: `bg-red-100 text-red-700`
- `webhook_ref`: `bg-teal-100 text-teal-700`
- `user_guide`: `bg-green-100 text-green-700`

**Status badge colors:**
- `planned`: `bg-gray-100 text-gray-600`
- `draft`: `bg-yellow-100 text-yellow-700`
- `published`: `bg-green-100 text-green-700`
- `archived`: `bg-red-100 text-red-600`

**Tier badge:**
- `fully_automated`: `bg-sky-100 text-sky-700` + robot/lightning icon
- `semi_automated`: `bg-violet-100 text-violet-700` + half-filled icon
- `human_authored`: `bg-amber-100 text-amber-700` + pencil icon

**Card hover effect**: `hover:shadow-lg hover:-translate-y-0.5 transition-all duration-150`

**Card border**: subtle `border border-gray-200 dark:border-gray-700`

If `content` is null (planned doc with no content yet): show a "Content not yet generated" subtext in italic gray.

### 5. Document Detail Page (`docs_detail.html`)

**Two-column layout:**
- Left column: `w-full lg:w-2/3` — document content
- Right column: `w-full lg:w-1/3` — metadata sidebar (sticky on desktop: `lg:sticky lg:top-6`)

**Left column — document header:**
- Document title: `text-3xl font-bold`
- Status badge + tier badge + version badge (`v{version}`) in a row
- Divider
- Rendered markdown content (use `render_markdown()` utility — same as design doc render in existing items)
- Prose styles: headings with anchor links, syntax-highlighted code (use the same highlight.js or pygments setup already in the dashboard), tables, blockquotes

**Right column — metadata sidebar:**
Four cards stacked vertically, each with a heading and content:

1. **Document** card: type (colored badge), editorial category, doc ID (monospace)
2. **Generation** card: generated at (absolute datetime), generated by (monospace generator slug), "Never generated" if null
3. **Sources** card: list of `source_paths` as `<code>` elements; "No sources defined" if empty
4. **Audience** card: chips for each audience value

**Action buttons** (below or in sidebar header):
- "Download PDF" button: `hx-get="/project/{id}/docs/{doc_id}/pdf"` — this triggers a page navigation (not htmx fragment), so use a regular `<a href="...">` with target `_blank`
- "Version History" button: `hx-get="/api/project/{id}/docs/{doc_id}/versions"`, `hx-target="#version-drawer"`, `hx-swap="innerHTML"`, toggles drawer open

**Version History Drawer:**
- Fixed-position slide-in panel from the right (or inline below sidebar)
- `id="version-drawer"`
- Populated via htmx from `docs_version_drawer.html` fragment
- Each version entry: version number (badge), created at, trigger reason (monospace), generator
- Close button: clears `#version-drawer` content (`hx-on:click="document.getElementById('version-drawer').innerHTML = ''"`)
- If no versions: "No version history yet"
- Smooth open animation: Tailwind `transition-all` on the drawer container

**No content placeholder:**
When `doc.content` is null, show a styled placeholder in the content area:
```
📄 Content not yet generated
This document is registered but has no content yet.
Use `iw doc-update {project_id} {doc_id} --content-file your-doc.md` to add content.
```

### 6. PDF Generation Route

`GET /project/{project_id}/docs/{doc_id}/pdf`

Implementation:
1. Fetch `ProjectDoc` by composite id — 404 if not found
2. 404 if `content` is null ("No content to generate PDF from")
3. If `pdf_path` is set and the file exists at that path → serve the cached file
4. If `pdf_path` is null OR cached file is missing → generate PDF on-demand:
   a. Render markdown to HTML using a minimal Jinja2 template (create `dashboard/templates/pdf/doc_pdf.html`)
   b. Convert HTML to PDF using WeasyPrint:
      ```python
      from weasyprint import HTML
      pdf_bytes = HTML(string=html_content).write_pdf()
      ```
   c. Write PDF to disk at `{project.repo_root}/docs/.generated/{project_id}/{doc_id}-v{version}.pdf`
   d. Update `doc.pdf_path` in DB via `DocService.update_doc(pdf_path=...)`
5. Return `Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{doc.slug}-v{doc.version}.pdf"'})`

**Fallback**: If WeasyPrint is not installed (`ImportError`), return 501 with JSON error `{"error": "PDF generation not available", "detail": "WeasyPrint is not installed. Run: pip install weasyprint"}`.

**Timeout**: Wrap the WeasyPrint call in `concurrent.futures.ThreadPoolExecutor`:
```python
import concurrent.futures
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(HTML(string=html_content).write_pdf)
    try:
        pdf_bytes = future.result(timeout=10)
    except concurrent.futures.TimeoutError:
        return JSONResponse({"error": "PDF generation timed out", "retry": true}, status_code=504)
```
Do NOT set `pdf_path` on the DB record if generation timed out.

**PDF HTML template** (`dashboard/templates/pdf/doc_pdf.html`):
- Minimal branded template
- AI Core color palette (not InnoForge brand)
- Title, version, generated at in header
- Rendered markdown content in body
- Page numbers in footer (WeasyPrint CSS: `@page { @bottom-center { content: counter(page); } }`)

### 7. Search Results Fragment (`docs_search_results.html`)

Returns only the card grid contents (no outer wrapper) for htmx to swap into `#docs-grid`. Reuses `docs_card.html` partial for each doc. Includes the empty state when results are empty.

## Elegance Requirements (NON-NEGOTIABLE)

These are hard requirements, not suggestions:

1. **No raw unstyled text** — every piece of data has appropriate typography treatment
2. **Color-coded badges** — all type, status, tier badges use distinct colors as specified
3. **Hover states** on all interactive elements (cards, buttons, nav items)
4. **Smooth transitions** — cards, drawer open/close, badge hover effects
5. **Dark mode awareness** — use `dark:` Tailwind variants matching how existing templates handle dark mode
6. **Mobile responsive** — every layout works at 320px width
7. **Consistent with existing dashboard** — no new CSS frameworks, no inline styles, no classes that don't exist in existing templates

## Test Verification (NON-NEGOTIABLE)

After implementation:
1. `make quality` — ruff + mypy must pass
2. Manually verify (or describe in report) that all routes return 200 with correct context

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "Frontend",
  "work_item": "F-00011",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/docs.py",
    "dashboard/templates/docs_library.html",
    "dashboard/templates/docs_detail.html",
    "dashboard/templates/fragments/docs_card.html",
    "dashboard/templates/fragments/docs_search_results.html",
    "dashboard/templates/fragments/docs_version_drawer.html",
    "dashboard/templates/fragments/nav_projects.html",
    "dashboard/templates/pdf/doc_pdf.html"
  ],
  "tests_passed": true,
  "test_summary": "quality checks passed",
  "blockers": [],
  "notes": ""
}
```
