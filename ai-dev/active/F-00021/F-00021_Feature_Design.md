# F-00021: Research Panel in AI Dashboard

**Type**: Feature
**Phase**: IW AI Core — Research System
**Priority**: High
**Created**: 2026-04-13
**Status**: Draft
**Repository**: `iw-ai-core` (``)

---

## Description

Adds a dedicated Research section to the IW AI Core dashboard. The panel provides a list
view of all research documents registered with `DocType.research`, a full-content detail
view with rendered markdown, and filtering by status and editorial category (which maps to
the research mode set by the `iw-research` skill). The panel follows the identical pattern
established by the existing Docs panel (`docs.py` / `docs_library.html` / `docs_detail.html`).

## Architecture References

| Document | Section | Relevance |
|----------|---------|-----------|
| `dashboard/routers/docs.py` | Full file | Pattern to follow for `research.py` router |
| `dashboard/templates/docs_library.html` | Full file | Template pattern for `research_library.html` |
| `dashboard/templates/docs_detail.html` | Full file | Template pattern for `research_detail.html` |
| `dashboard/templates/base.html:127` | Sidebar "Docs" link | Add "Research" link below it |
| `dashboard/app.py:104` | `app.include_router(docs.router)` | Add research router here |
| `orch/doc_service.py:225` | `list_docs(doc_type=...)` | Filter by `DocType.research` |
| `orch/db/models.py:150` | `DocType` enum | `DocType.research` added in F-00020 |

## Scope

### In Scope

- `dashboard/routers/research.py` — two endpoints: `/research` (list) and `/research/{doc_id}` (detail)
- `dashboard/templates/research_library.html` — list view with search, status filter, category filter
- `dashboard/templates/research_detail.html` — detail view with rendered markdown + version history
- `dashboard/templates/base.html` — add "Research" sidebar link below "Docs"
- `dashboard/app.py` — register the new router
- Integration tests for both new routes

### Out of Scope

- Any changes to `DocType` or `WorkItemType` enums (F-00020)
- Editing research documents from the dashboard
- Creating research items from the dashboard (skill-only workflow)
- Source citation rendering (research docs are plain markdown — citations are embedded text)

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | Router + templates + navigation | — |
| S02 | CodeReview_Frontend | Review S01 | — |
| S03 | Tests | Integration tests for research routes | after S02 |
| S04 | CodeReview_Final | Global review | — |
| S05–S11 | QV Gates | lint, format, typecheck, arch, security, integration | — |
| S12 | QV Browser | Screenshot research panel | after S11 |

### Database Changes

- None (uses existing `ProjectDoc` table filtered by `DocType.research`)

### API Changes

- None (dashboard-only routes, not in the main `innoforge` API)

### Frontend Changes (Dashboard)

- **New router**: `dashboard/routers/research.py`
- **New templates**: `research_library.html`, `research_detail.html`
- **Modified**: `base.html` (sidebar link), `app.py` (router registration)

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `F-00021_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Orchestrator step definitions |
| `prompts/F-00021_S01_Frontend_prompt.md` | Prompt | Router + templates + nav |
| `prompts/F-00021_S02_CodeReview_Frontend_prompt.md` | Prompt | Review S01 |
| `prompts/F-00021_S03_Tests_prompt.md` | Prompt | Integration tests |
| `prompts/F-00021_S04_CodeReview_Final_prompt.md` | Prompt | Global review |
| `prompts/F-00021_S12_QVBrowser_prompt.md` | Prompt | Browser screenshot |
| `reports/` | Directory | Created during execution |
| `evidences/pre/F-00021-before.png` | Evidence | Captured during development |
| `evidences/post/F-00021-after.png` | Evidence | Captured by QV Browser step |

## Acceptance Criteria

### AC1: Research list page

```
Given at least one ProjectDoc with doc_type = 'research' exists
When I navigate to /project/{id}/research
Then I see a list of research documents with ID, title, status, category, and date
And I can filter by status (draft/published/archived)
And I can filter by editorial_category (technical/marketing/functional/etc.)
```

### AC2: Research detail page

```
Given a research document R-00001 exists with markdown content
When I navigate to /project/{id}/research/R-00001
Then I see the rendered markdown content
And I see the document metadata (title, status, category, created date)
And I see the version history list
```

### AC3: Empty state

```
Given no research documents exist for the project
When I navigate to /project/{id}/research
Then I see an empty-state message (not an error)
```

### AC4: 404 on unknown ID

```
Given no research document with ID R-99999 exists
When I navigate to /project/{id}/research/R-99999
Then I receive a 404 HTTP response
```

### AC5: Sidebar navigation

```
Given I am on any dashboard page
When I look at the sidebar
Then I see a "Research" link that navigates to /project/{id}/research
And the link is highlighted when I am on the research pages
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| No research docs | Empty `project_docs` for DocType.research | Empty state, no error |
| Unknown doc_id | `R-99999` not in DB | HTTP 404 |
| Doc with no content | `content = NULL` | Detail page renders gracefully, no 500 |
| Doc with very long markdown | >100KB content | Rendered with possible truncation, no 500 |
| Non-research doc accessed via research route | A `module` doc_id accessed at `/research/{id}` | HTTP 404 (type mismatch guard) |

## Invariants

1. `/project/{id}/research` only returns docs with `doc_type = DocType.research`
2. `/project/{id}/research/{doc_id}` returns 404 for docs that exist but have a different doc_type
3. No 500 errors for any valid URL shape

## Dependencies

- **Depends on**: F-00020 (must be deployed first so `DocType.research` exists in the DB)
- **Blocks**: Nothing directly

## TDD Approach

Integration tests in `tests/integration/test_dashboard_pages.py` (iw-ai-core):

- `test_research_library_page_empty`: GET `/project/{id}/research` with no research docs → 200 + empty state
- `test_research_library_page_with_docs`: GET `/project/{id}/research` with seeded research doc → 200 + doc listed
- `test_research_detail_page`: GET `/project/{id}/research/R-00001` with content → 200 + content rendered
- `test_research_detail_page_404`: GET `/project/{id}/research/R-99999` → 404
- `test_research_detail_wrong_type_404`: GET `/project/{id}/research/{module_doc_id}` → 404

## Notes

**Editorial category as research mode**: The `editorial_category` field is used as a proxy
for the research mode set by the `iw-research` skill:
- `technical` → tech research
- `marketing` → market research
- `functional` → deep or general research

The dashboard displays the raw `editorial_category` value. No translation layer needed in
this feature — the skill documentation handles the mapping.

**Single-repository**: All code changes, design docs, and reports live in `iw-ai-core/ai-dev/active/F-00021/`.
