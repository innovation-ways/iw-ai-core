# F-00011: Project-Level Documentation System — Foundation (Phase 1)

**Type**: Feature
**Priority**: Medium
**Created**: 2026-04-13
**Status**: Draft

---

## Description

Introduces a project-level documentation system into AI Core as a first-class platform capability. Adds three new database tables (`ProjectDoc`, `ProjectDocVersion`, `DocGenerationJob`), an Alembic migration, an `iw doc-update` CLI command (with full metadata flags) for AI agents to write documentation content back into the database, and a new "Docs" sidebar tab per project with an elegant card-grid library view and a full document detail/render view including PDF export.

This is Phase 1 of a multi-phase AI-driven documentation feature. It establishes the foundation — data model, CLI contract, and UI — that Phases 2 (AI generation automation), 3 (event-triggered regeneration), and 4 (cross-project search and diff) will build upon.

The design is aligned with the InnoForge documentation strategy (`docs/documentation-strategy.md`): Markdown-first, YAML frontmatter, three automation tiers (fully automated / semi-automated / human-authored), editorial categories, and version history. Unlike InnoForge, the doc catalog is PostgreSQL-backed (not JSON files), making it queryable and UI-browsable.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key constraints:
- **NEVER** connect tests to live DB (port 5433) — testcontainers only
- **NEVER** mock the database in integration tests
- **MUST** replace psycopg2 URLs in testcontainers
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in tests
- All config via `.env` — **NEVER** hardcode ports, URLs, or credentials

## Scope

### In Scope

- `ProjectDoc` SQLAlchemy model: full document metadata (id, project_id, doc_id, title, slug, doc_type enum, tier enum, editorial_category enum, status enum, source_paths, audience, content TEXT, content_search TSVECTOR, version, generated_at, generated_by, html_path, pdf_path)
- `ProjectDocVersion` SQLAlchemy model: immutable version snapshots of doc content
- `DocGenerationJob` SQLAlchemy model: tracks async AI generation job state
- Alembic migration covering all three new tables, FTS trigger for `ProjectDoc.content_search`
- `DocService` repository class: CRUD operations, FTS query, version snapshot creation, staleness detection
- `iw doc-update` CLI command with flags: `--content`, `--status`, `--version`, `--source-paths`, `--editorial-category`, `--audience`, `--title`, `--slug`; accepts content from file path or stdin
- New "Docs" sidebar nav entry per project → `/project/{project_id}/docs`
- Doc library page: responsive card grid, filter by `doc_type` and `status`, full-text search bar (htmx-powered)
- Document detail page: rendered markdown (prose-doc styled), metadata sidebar (type, status, version, generated at, sources, editorial category, audience), version history drawer, "Download PDF" button
- PDF rendering: server-side HTML → PDF conversion via WeasyPrint/Playwright, served as a file download
- Elegant, modern UI: consistent with existing dashboard style (Tailwind CSS, htmx, dark-mode aware)

### Out of Scope

- AI agent orchestration that calls the generation skills (Phase 2)
- Daemon-triggered automatic regeneration on batch merge (Phase 3)
- Version diffing between doc versions (Phase 4)
- Cross-project global documentation search (Phase 4)
- Public documentation site or Docusaurus integration
- Per-project editorial guidelines storage in DB
- Brand customization per project (uses AI Core brand defaults)

## Architecture References

| Existing Pattern | Location | How We Extend It |
|----------------|----------|-----------------|
| `WorkItem` model with `design_doc_content` + `design_doc_search` | `orch/db/models.py` | Same Tier 1 TEXT + TSVECTOR pattern for `ProjectDoc` |
| FTS trigger constants `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` | `orch/db/models.py` | Add equivalent trigger for `project_docs` table |
| `iw step-done` CLI command | `orch/cli/step_commands.py` | New `iw doc-update` command in a new `doc_commands.py` |
| Project sidebar nav (7 tabs) | `dashboard/templates/fragments/nav_projects.html` | Add 8th tab: Docs |
| Item design doc render | `dashboard/routers/items.py`, `item_design_doc.html` | Re-use `render_markdown()` utility, extend prose-doc styles |
| htmx fragment routes | `dashboard/routers/project_pages.py` | New `docs.py` router with library + detail fragments |
| Batch status cards | `dashboard/templates/fragments/` | Model doc library cards on same card pattern |

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Database | `ProjectDoc`, `ProjectDocVersion`, `DocGenerationJob` models + Alembic migration + FTS trigger | — |
| S02 | Backend | `DocService`: CRUD, FTS query, version snapshot, staleness detection | — |
| S03 | CodeReview_Backend | Review S01 + S02 output | — |
| S04 | API | `iw doc-update` CLI command (`orch/cli/doc_commands.py`) | S05 |
| S05 | Frontend | Docs tab: library view + detail view + PDF download route | S04 |
| S06 | Tests | Unit tests (DocService, doc_commands), integration tests (routes, CLI, DB) | — |
| S07 | CodeReview_Final | Global cross-layer review of all steps | — |
| S08 | QV | lint (`make lint`) | — |
| S09 | QV | format (`make format`) | — |
| S10 | QV | typecheck (`make typecheck`) | — |
| S11 | QV | unit-tests (`make test-unit`) | — |
| S12 | QV | integration-tests (`make allure-integration`) | — |

### Database Changes

**New tables:**
- `project_docs` — primary doc catalog per project
- `project_doc_versions` — immutable version snapshots
- `doc_generation_jobs` — async AI generation job tracking

**Modified tables:** None

**Migration notes:**
- Create FTS trigger `trg_project_docs_fts` on `project_docs` table (same pattern as `trg_work_items_fts`)
- `doc_type` PostgreSQL ENUM: `module`, `api`, `architecture`, `release_notes`, `error_catalog`, `webhook_ref`, `user_guide`
- `doc_tier` PostgreSQL ENUM: `fully_automated`, `semi_automated`, `human_authored`
- `editorial_category` PostgreSQL ENUM: `technical`, `functional`, `guide`, `compliance`, `marketing`, `release`
- `doc_status` PostgreSQL ENUM: `planned`, `draft`, `published`, `archived`
- `job_status` PostgreSQL ENUM: `queued`, `running`, `completed`, `failed`

### API Changes

**New CLI command:**
- `iw doc-update <project_id> <doc_id> [options]` — upserts a `ProjectDoc` record and creates a `ProjectDocVersion` snapshot

**New dashboard routes (in `dashboard/routers/docs.py`):**
- `GET /project/{project_id}/docs` — doc library page
- `GET /project/{project_id}/docs/{doc_id}` — document detail page
- `GET /project/{project_id}/docs/{doc_id}/pdf` — serve PDF file download
- `GET /api/project/{project_id}/docs/search` — htmx FTS search fragment
- `GET /api/project/{project_id}/docs/filter` — htmx filter fragment

**Modified dashboard routes:**
- `dashboard/routers/__init__.py` or app factory — register new `docs` router

### Frontend Changes

**New templates:**
- `dashboard/templates/docs_library.html` — full library page
- `dashboard/templates/fragments/docs_card.html` — individual doc card (htmx target)
- `dashboard/templates/docs_detail.html` — full document detail page
- `dashboard/templates/fragments/docs_version_drawer.html` — version history drawer

**Modified templates:**
- `dashboard/templates/fragments/nav_projects.html` — add Docs nav entry (8th tab)

## Data Models

### ProjectDoc

```python
class ProjectDoc(Base):
    __tablename__ = "project_docs"

    id: Mapped[str]                    # PK — "{project_id}:{doc_id}" composite slug
    project_id: Mapped[str]            # FK → projects.id
    doc_id: Mapped[str]                # User-defined doc identifier (e.g., "module-auth", "api-reference")
    title: Mapped[str]
    slug: Mapped[str]                  # URL-safe identifier
    doc_type: Mapped[DocType]          # ENUM: module | api | architecture | release_notes | error_catalog | webhook_ref | user_guide
    tier: Mapped[DocTier]              # ENUM: fully_automated | semi_automated | human_authored
    editorial_category: Mapped[EditorialCategory]  # ENUM: technical | functional | guide | compliance | marketing | release
    status: Mapped[DocStatus]          # ENUM: planned | draft | published | archived
    audience: Mapped[list[str]]        # JSONB array (e.g., ["architects", "senior-developers"])
    source_paths: Mapped[list[str]]    # JSONB array of source file paths
    content: Mapped[str | None]        # Tier 1: full markdown content
    content_search: Mapped[any]        # TSVECTOR (auto-updated by trigger)
    version: Mapped[int]               # Monotonically increasing
    generated_at: Mapped[datetime | None]
    generated_by: Mapped[str | None]   # e.g., "skill:iw-doc-generator" or "human"
    html_path: Mapped[str | None]      # Relative path to rendered HTML file
    pdf_path: Mapped[str | None]       # Relative path to rendered PDF file
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

### ProjectDocVersion

```python
class ProjectDocVersion(Base):
    __tablename__ = "project_doc_versions"

    id: Mapped[int]                    # PK (BIGSERIAL)
    doc_id: Mapped[str]                # FK → project_docs.id
    version: Mapped[int]               # Version number at time of snapshot
    content: Mapped[str]               # Markdown content snapshot
    generated_by: Mapped[str | None]
    trigger_reason: Mapped[str | None] # e.g., "manual", "batch-merge:B-00042", "cli:iw doc-update"
    created_at: Mapped[datetime]
```

### DocGenerationJob

```python
class DocGenerationJob(Base):
    __tablename__ = "doc_generation_jobs"

    id: Mapped[str]                    # PK (UUID)
    project_id: Mapped[str]            # FK → projects.id
    doc_id: Mapped[str]                # FK → project_docs.id (composite)
    status: Mapped[JobStatus]          # ENUM: queued | running | completed | failed
    requested_at: Mapped[datetime]
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    agent_output: Mapped[str | None]   # Raw agent stdout/result
    error: Mapped[str | None]          # Error message if failed
    created_at: Mapped[datetime]
```

## CLI Contract: `iw doc-update`

```
Usage: iw doc-update PROJECT_ID DOC_ID [OPTIONS]

  Upsert a project documentation record. Creates or updates the ProjectDoc
  for the given project and doc ID. If the doc already exists and content
  changed, a new ProjectDocVersion snapshot is created automatically.

Arguments:
  PROJECT_ID  The project identifier (e.g., "innoforge")
  DOC_ID      The doc identifier within the project (e.g., "module-auth")

Options:
  --title TEXT                  Document title
  --slug TEXT                   URL-safe slug (auto-derived from title if omitted)
  --doc-type [module|api|architecture|release_notes|error_catalog|webhook_ref|user_guide]
  --tier [fully_automated|semi_automated|human_authored]
  --editorial-category [technical|functional|guide|compliance|marketing|release]
  --status [planned|draft|published|archived]
  --audience TEXT               Comma-separated list (e.g., "architects,senior-developers")
  --source-paths TEXT           Comma-separated list of source file paths
  --content TEXT                Markdown content (mutually exclusive with --content-file)
  --content-file PATH           Path to markdown file (use "-" for stdin)
  --generated-by TEXT           Generator identifier (e.g., "skill:iw-doc-generator")
  --trigger-reason TEXT         Reason for this update (stored in version snapshot)
  --version INTEGER             Override version number (default: auto-increment)
  --help                        Show this message and exit.
```

**Output (stdout):**
```json
{
  "doc_id": "innoforge:module-auth",
  "project_id": "innoforge",
  "version": 3,
  "status": "draft",
  "snapshot_created": true
}
```

**Exit codes:** 0 = success, 1 = project not found, 2 = validation error, 3 = DB error

## UI Design: Docs Tab

### Library Page (`/project/{project_id}/docs`)

**Layout:**
- Page header: "Documentation" title + "Register Doc" button (Phase 2 will add "Generate" button)
- Filter bar: doc_type pills (All | Module | API | Architecture | ...) + status pills (All | Draft | Published) + search input (htmx-powered FTS)
- Card grid: 3 columns on desktop, 2 on tablet, 1 on mobile
- Empty state: illustrated empty state with explanation and link to CLI docs

**Doc Card:**
- Doc type badge (color-coded: blue=architecture, green=api, purple=module, etc.)
- Title (large, bold)
- Tier badge: Automated / Semi-Auto / Human
- Status badge: Draft (yellow) / Published (green) / Planned (gray) / Archived (red)
- Last generated: relative time ("2 hours ago") + absolute on hover
- Version: "v3"
- Source count: "3 sources"
- Actions: "View" button → detail page

### Document Detail Page (`/project/{project_id}/docs/{doc_id}`)

**Layout:** Two-column (content left 70%, metadata sidebar right 30%)

**Left column:**
- Document header: title + status badge + version badge
- Rendered markdown content (prose-doc styles — same as existing design doc render)
- Syntax-highlighted code blocks
- Tables, blockquotes, diagrams (inline images from `_diagrams/`)

**Right sidebar:**
- **Metadata card:** type, tier, editorial category, status
- **Generation card:** generated at (absolute), generated by (generator slug)
- **Sources card:** list of source paths as links (if they exist in repo)
- **Audience card:** chips for each audience type
- **Actions:** "Download PDF" button, "Version History" button (opens drawer)

**Version History Drawer (htmx-toggled):**
- Scrollable list of all `ProjectDocVersion` records
- Each entry: version number, created at, trigger reason, generator
- No diff in Phase 1 — just the list

### PDF Download Route

`GET /project/{project_id}/docs/{doc_id}/pdf`

- If `pdf_path` exists and file is present → serve directly as `application/pdf` with `Content-Disposition: attachment`
- If `pdf_path` is null → generate on-demand: render markdown → HTML (Jinja2) → PDF (WeasyPrint) → serve → cache path in DB
- 10-second timeout with loading spinner (htmx polling)

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00011/F-00011_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00011/workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `ai-dev/active/F-00011/prompts/F-00011_S01_Database_prompt.md` | Prompt | DB models + migration |
| `ai-dev/active/F-00011/prompts/F-00011_S02_Backend_prompt.md` | Prompt | DocService repository |
| `ai-dev/active/F-00011/prompts/F-00011_S03_CodeReview_Backend_prompt.md` | Prompt | Review S01+S02 |
| `ai-dev/active/F-00011/prompts/F-00011_S04_API_prompt.md` | Prompt | iw doc-update CLI command |
| `ai-dev/active/F-00011/prompts/F-00011_S05_Frontend_prompt.md` | Prompt | Docs tab UI |
| `ai-dev/active/F-00011/prompts/F-00011_S06_Tests_prompt.md` | Prompt | Unit + integration tests |
| `ai-dev/active/F-00011/prompts/F-00011_S07_CodeReview_Final_prompt.md` | Prompt | Final cross-layer review |

Reports created during execution in `ai-dev/work/F-00011/reports/`.

## Acceptance Criteria

### AC1: Docs tab visible in project navigation

```
Given a registered project exists in the platform
When the user navigates to any project page
Then the sidebar shows "Docs" as the 8th navigation item
And clicking it navigates to /project/{project_id}/docs
```

### AC2: Doc library renders with filter and search

```
Given a project has 3 ProjectDoc records (one module, one api, one architecture)
When the user visits /project/{project_id}/docs
Then all 3 docs are displayed as cards with correct type badges and status badges
When the user clicks the "API" filter pill
Then only the api doc card is shown (htmx fragment reload)
When the user types "auth" in the search bar
Then only docs whose title or content matches "auth" are shown
```

### AC3: iw doc-update creates doc and version snapshot

```
Given project "innoforge" is registered
When the agent runs: iw doc-update innoforge module-auth --title "Auth Module" --doc-type module --content-file auth.md --status draft --tier semi_automated
Then a ProjectDoc record is created (or updated) with the provided metadata
And a ProjectDocVersion snapshot is created with version=1 and trigger_reason="cli:iw doc-update"
And the CLI exits with code 0 and prints JSON with the doc_id and version
```

### AC4: Document detail renders elegantly with metadata sidebar

```
Given a ProjectDoc record exists with content and metadata
When the user navigates to /project/{project_id}/docs/{doc_id}
Then the markdown content is rendered as styled HTML in the left column
And the right sidebar shows metadata: type, tier, editorial category, status, version, generated at, source paths, audience
And the "Version History" button is present
```

### AC5: Version history drawer shows all snapshots

```
Given a ProjectDoc has been updated 3 times via iw doc-update
Then ProjectDocVersion contains 3 rows for that doc
When the user clicks "Version History" on the detail page
Then the drawer opens listing all 3 versions with their version number, created at, and trigger reason
```

### AC6: PDF download is served correctly

```
Given a ProjectDoc with markdown content exists
When the user clicks "Download PDF" on the detail page
Then the server renders the markdown to HTML and converts to PDF
And the browser receives a file download with Content-Disposition: attachment; filename="{slug}-v{version}.pdf"
And the pdf_path is cached on the ProjectDoc record for subsequent requests
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Docs tab with no docs | Project has 0 ProjectDoc records | Library page shows illustrated empty state with explanation |
| iw doc-update on non-existent project | `iw doc-update unknown-proj doc-1` | Exit code 1, error message: "Project 'unknown-proj' not found" |
| iw doc-update content unchanged | Same content as current version | Update metadata only, do NOT create a new version snapshot (content hash check) |
| iw doc-update with --content-file "-" | Stdin pipe | Reads content from stdin correctly |
| FTS search with no results | Query matches no docs | Shows "No documents match your search" message (not an error) |
| PDF generation timeout | Rendering takes >10 seconds | Returns 504 with retry instruction; does not cache a broken path |
| PDF cached but file deleted | `pdf_path` set but file missing | Re-generates PDF on demand, updates cached path |
| Version history with 1 version | One snapshot only | Drawer shows single entry without error |
| Doc with no content (planned) | `content` is NULL | Detail page shows "Content not yet generated" placeholder |
| Filter + search combined | Both active simultaneously | Intersection: results must match both type filter AND search query |
| Oversized content input | Content ≥ 10 MB via `--content` or stdin | CLI rejects with exit code 2 and message "Content exceeds maximum size (10 MB)" |

## Invariants

1. Every `ProjectDocVersion` row has an associated `ProjectDoc` row (FK enforced)
2. `ProjectDoc.version` is always equal to the count of `ProjectDocVersion` rows for that doc (enforced by `DocService.update_doc`)
3. A new `ProjectDocVersion` snapshot is created if and only if the content has changed (hash comparison)
4. `ProjectDoc.content_search` is always up to date with `content` (enforced by DB trigger)
5. `iw doc-update` is idempotent: running it twice with identical arguments produces no new version snapshot
6. `ProjectDoc.id` is always `"{project_id}:{doc_id}"` — never arbitrary UUIDs
7. PDF path is only set on `ProjectDoc` if the file was successfully generated and written to disk

## Dependencies

- **Depends on**: None — Project model already exists; FTS pattern already established
- **Blocks**: F-00012 (Phase 2: AI Generation), F-00013 (Phase 3: Automation), F-00014 (Phase 4: Polish)

## TDD Approach

**Unit tests** (`tests/unit/`):
- `DocService.create_doc()`: creates record with correct defaults
- `DocService.update_doc()`: increments version, creates snapshot on content change, skips snapshot when content unchanged
- `DocService.search_docs()`: FTS query returns ranked results
- `DocService.get_stale_docs()`: returns docs whose source_paths have newer mtime than generated_at
- `doc_commands.py`: CLI argument parsing, content-from-file, content-from-stdin, exit codes

**Integration tests** (`tests/integration/`):
- Full roundtrip: `iw doc-update` → DB record created → version snapshot created
- Dashboard route `GET /project/{id}/docs` returns 200 with cards
- Dashboard route `GET /project/{id}/docs/{doc_id}` returns 200 with rendered markdown
- FTS search: insert doc, search by keyword, assert result appears
- PDF route: returns `application/pdf` response
- Version history route: returns correct version list
- Empty state: project with no docs returns 200 with empty state HTML

## Notes

**InnoForge alignment decisions:**
- `doc_id` format follows InnoForge's catalog ID pattern (e.g., `module-auth`, `api-reference`) — human-readable slugs, not UUIDs
- `editorial_category` enum maps 1:1 to InnoForge's `doc-system/editorial/` categories
- `tier` enum maps to InnoForge's Tier 1 / Tier 2 / Tier 3 automation classification
- `source_paths` on `ProjectDoc` mirrors InnoForge catalog's `source_dependencies` — enables staleness detection in Phase 3
- YAML frontmatter fields (`generated_at`, `generated_by`, `audience`) are stored as structured DB columns, not parsed from content on every read

**CLI command style:**
- The command is `iw doc-update` (flat, hyphenated) — consistent with existing CLI commands (`iw step-done`, `iw batch-approve`, `iw item-status`). S04 prompt should use flat command style.

**`html_path` field:**
- Stored for future use (Phase 2+) when AI generation skills may pre-render and cache HTML. In Phase 1, this field is never written by any route or CLI command — it is reserved. S02 `DocService.update_doc()` should accept `html_path` as an optional parameter so it can be set programmatically, but no Phase 1 code sets it.

**PDF rendering:**
- WeasyPrint is the primary renderer (already used in InnoForge doc-system); install via `pip install weasyprint`
- Fallback: if WeasyPrint system libraries are unavailable, use Playwright chromium (already available via `playwright-cli`)
- PDF template: minimal branded Jinja2 template with AI Core color palette (not InnoForge brand — this is the AI Core platform)
- Font: system sans-serif (no external font dependencies for Phase 1)
- PDF generation timeout: implemented via `concurrent.futures.ThreadPoolExecutor` with a 10-second `future.result(timeout=10)` call around WeasyPrint. On `TimeoutError`, return HTTP 504 with JSON `{"error": "PDF generation timed out", "retry": true}`. Do NOT cache `pdf_path` on timeout.

**UI elegance requirements for S05 Frontend:**
- Cards must use smooth hover shadows and transitions (Tailwind `hover:shadow-lg transition-shadow`)
- Type badges must be distinctly color-coded (not all the same color)
- Status badges must use semantic colors (green=published, yellow=draft, gray=planned, red=archived)
- Markdown render must support: headings with anchor links, syntax-highlighted code, tables, blockquotes, inline badges
- The detail page must feel like reading a polished document, not a raw markdown dump
- Version history drawer must animate open/close (Tailwind transition classes)
- Mobile-responsive at every breakpoint
