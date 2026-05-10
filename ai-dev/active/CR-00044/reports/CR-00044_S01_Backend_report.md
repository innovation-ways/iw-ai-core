# CR-00044 S01 Backend Implementation Report

## What Was Done

### 1. `GET /favicon.ico` route (`dashboard/app.py`)
- Added `GET /favicon.ico` registered directly on the app object, next to `GET /health`
- Returns `dashboard/static/favicon.svg` via `FileResponse` with `media_type="image/svg+xml"`
- Defensive 204 if SVG is missing (satisfies **AC5**)

### 2. Subdirectory-capable docs viewer (`dashboard/routers/system.py`)
- Replaced `GET /docs/{doc_slug}` (regex `^[A-Za-z0-9_]+$`) with `GET /docs/{doc_path:path}`
- Precomputed `_DOC_URL_MAP` at module load: maps URL key → repo-relative path for:
  - All `docs/**/*.md` files (recursive, URL key = relative path with `.md` stripped)
  - Curated `CLAUDE.md` files: `orch/rag/CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `executor/CLAUDE.md`
- Validation (in order): reject empty/leading-`/` / `.` / `..` path components → dict lookup → resolved-path inside allowed base dirs → require `.md` file
- Page title from first H1 via `_extract_h1_title()`; fallback to stem with underscores (satisfies **AC1, AC2, AC3, AC6**)

### 3. Updated `_SLUG_TO_DOC` mappings (`dashboard/routers/help.py`)
- `code` → `/system/docs/orch/rag/CLAUDE.md`
- `item_detail` → `/system/docs/IW_AI_Core_Dashboard_Design#45-work-item-detail-projectiditemitem_id`
- `research` → `/system/docs/IW_AI_Core_Dashboard_Design`
- `search` → `/system/docs/IW_AI_Core_Dashboard_Design`
- `projects` unchanged → `/system/docs/IW_AI_Core_Architecture`
- The `#45-work-item-detail-projectiditemitem_id` anchor was verified to exist in the rendered output of `IW_AI_Core_Dashboard_Design.md` (from the `toc` extension) (satisfies **AC4**)

### 4. Updated `dashboard/CLAUDE.md`
- Updated the `system.py` row in the routers table to note `{doc_path:path}` form and the `docs/**/*.md` + curated `CLAUDE.md` scope

## Files Changed

- `dashboard/app.py` — added `GET /favicon.ico` route
- `dashboard/routers/system.py` — replaced slug route with subdirectory-capable path route
- `dashboard/routers/help.py` — updated `_SLUG_TO_DOC` mappings for CR-00044
- `dashboard/CLAUDE.md` — updated docs-view description
- `tests/dashboard/test_system_docs_route.py` — added `TestSystemDocsSubdirectory` class (9 new tests)
- `tests/dashboard/test_favicon.py` — new file (3 tests for favicon route)
- `tests/dashboard/test_help_router.py` — added `TestHelpRouterSlugMappingCR00044` class (5 new tests)

## Test Results

All 17 targeted tests pass:
- `tests/dashboard/test_favicon.py::TestFaviconRoute` — 3 passed
- `tests/dashboard/test_system_docs_route.py::TestSystemDocsSubdirectory` — 9 passed
- `tests/dashboard/test_help_router.py::TestHelpRouterSlugMappingCR00044` — 5 passed

## Preflight Quality Gates

| Gate | Result |
|------|-------|
| `make format` | ok (2 test files auto-formatted by ruff, then clean) |
| `make typecheck` | ok (no issues in 240 source files) |
| `make lint` | ok (all checks passed) |

## Anchors Added to `_SLUG_TO_DOC` and Verification

| Slug | Target | Anchor | Verified? |
|------|--------|--------|-----------|
| `code` | `/system/docs/orch/rag/CLAUDE.md` | None (no stable section id) | N/A |
| `item_detail` | `/system/docs/IW_AI_Core_Dashboard_Design` | `#45-work-item-detail-projectiditemitem_id` | Yes — exists in rendered HTML from toc extension |
| `research` | `/system/docs/IW_AI_Core_Dashboard_Design` | None (no "research" heading id found) | N/A |
| `search` | `/system/docs/IW_AI_Core_Dashboard_Design` | None (no "search" heading id found) | N/A |
| `projects` | `/system/docs/IW_AI_Core_Architecture` | None | N/A |
| `queue` | `/system/docs/IW_AI_Core_CLI_Spec` | `#iw-approve` | Pre-existing (CR-00042) |

The `research` and `search` slugs have no stable heading id in `IW_AI_Core_Dashboard_Design.md` that would make sense for them, so they ship without anchors per the design requirement.

## Curated CLAUDE.md Allow-List

Added the following to `_CLAUDE_MD_PATHS`:
- `orch/rag/CLAUDE.md` — required for the `code` help link
- `orch/CLAUDE.md` — top-level orch docs, useful reference
- `dashboard/CLAUDE.md` — dashboard docs, useful reference
- `executor/CLAUDE.md` — executor docs, useful reference

Not bulk-added — kept intentional and short per the design note.