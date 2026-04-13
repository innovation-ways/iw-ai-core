# F-00041: Interactive Document IDE — Guide Editor & Diff Viewer UI

**Type**: Feature
**Phase**: Interactive Document IDE — Foundation Layer
**Priority**: High
**Created**: 2026-04-13
**Status**: Draft
**Repository**: `iw-ai-core`

---

## Description

Adds the "IDE" tab to the document detail page (`docs_detail.html`). The tab contains two panels:
a **Guide Editor** (type guide, instance guide, and per-section guides — all inline-editable via
htmx) and a **Section Diff Viewer** (consumes the new `diff/sections` endpoints from F-00040,
replacing the old flat unified-diff panel). The tab is rendered as an htmx fragment and lazy-
loaded only when the user clicks it. All edits are persisted via new htmx POST endpoints added
to `dashboard/routers/docs.py` that call the service methods from F-00037/F-00038/F-00039.

## Project Context

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, and `tests/CLAUDE.md` for architecture, conventions, and hard rules before implementing or reviewing.

## Architecture References

| File | Relevance |
|------|-----------|
| `dashboard/templates/docs_detail.html` | Page receiving the new IDE tab |
| `dashboard/templates/fragments/docs_diff.html` | Existing diff fragment (preserved; IDE tab adds new section diff) |
| `dashboard/routers/docs.py` | New htmx CRUD endpoints for guide editing |
| `orch/doc_service.py` | Service methods for all guide CRUD (F-00037/F-00038/F-00039) |
| `ai-dev/active/F-00037/F-00037_Feature_Design.md` | Type guide service methods |
| `ai-dev/active/F-00038/F-00038_Feature_Design.md` | Instance guide service methods |
| `ai-dev/active/F-00039/F-00039_Feature_Design.md` | Section guide service methods + `extract_sections` |
| `ai-dev/active/F-00040/F-00040_Feature_Design.md` | Section diff endpoints consumed here |

## Scope

### In Scope

**New htmx endpoints** in `dashboard/routers/docs.py`:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/project/{id}/api/docs/{doc_id}/ide` | Load IDE tab HTML fragment |
| `GET` | `/project/{id}/api/docs/{doc_id}/guide/type` | Load type guide editor panel |
| `POST` | `/project/{id}/api/docs/{doc_id}/guide/type` | Save type guide (calls `DocService.save_type_guide`) |
| `GET` | `/project/{id}/api/docs/{doc_id}/guide/instance` | Load instance guide editor panel |
| `POST` | `/project/{id}/api/docs/{doc_id}/guide/instance` | Save instance guide (calls `DocService.save_instance_guide`) |
| `DELETE` | `/project/{id}/api/docs/{doc_id}/guide/instance` | Delete instance guide |
| `GET` | `/project/{id}/api/docs/{doc_id}/guide/sections` | Load section guide list panel |
| `POST` | `/project/{id}/api/docs/{doc_id}/guide/sections/{section_name}` | Save a section guide |
| `DELETE` | `/project/{id}/api/docs/{doc_id}/guide/sections/{section_name}` | Delete a section guide |

**New Jinja2 template fragments**:

- `fragments/docs_ide_tab.html` — IDE tab container (guide editor + diff viewer panels in a two-column layout)
- `fragments/docs_guide_type_editor.html` — Type guide editor (markdown textarea + save button; read-only hint that this is the doc_type default)
- `fragments/docs_guide_instance_editor.html` — Instance guide editor (markdown textarea + save/delete; shows "inheriting from type guide" message if no instance override)
- `fragments/docs_guide_sections_panel.html` — Section guide list with per-section inline edit; sections extracted via `extract_sections(doc.content)` at render time; "No H2 sections — editing 'Document' guide" shown when applicable
- `fragments/docs_section_diff_panel.html` — Section diff viewer; consumes `/diff/sections?v1=N&v2=N`; tabs per section (only changed sections shown by default); "identical" badge for unchanged sections

**Tab registration** on `docs_detail.html`: Add "IDE" tab link that lazy-loads `/api/project/{id}/docs/{doc_id}/ide` via htmx on click (hx-get, hx-trigger="click", hx-swap="innerHTML", hx-target="#ide-panel").

**Integration tests** for all new endpoints: guide load, save, delete, section list renders, diff panel renders.

### Out of Scope

- AI-powered guide suggestions (future)
- Drag-and-drop section reordering
- Guide version history
- Markdown preview rendering (textarea only; no split-pane preview in this phase)
- Mobile layout optimization

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Frontend | New htmx endpoints in `docs.py`; all 5 template fragments; IDE tab on `docs_detail.html` | — |
| S02 | CodeReview_Frontend | Review S01 | — |
| S03 | Tests | Integration tests for all new GET/POST/DELETE endpoints | S02 complete |
| S04 | CodeReview_Final | Global review | S03 complete |
| S05 | QV: lint | `ruff check dashboard/ tests/` | — |
| S06 | QV: format | `ruff format --check dashboard/ tests/` | — |
| S07 | QV: typecheck | `mypy dashboard/routers/docs.py` | — |
| S08 | QV: integration-tests | `pytest tests/integration/ -x -q` | — |
| S09 | QVBrowser | Playwright: open docs detail, click IDE tab, verify panels load | S08 complete |

### Database Changes

- **None** — all writes go through service methods from F-00037/F-00038/F-00039

### API Changes

- **New endpoints**: 9 htmx endpoints (listed in scope above)
- **Modified templates**: `docs_detail.html` — IDE tab added
- **New fragments**: 5 Jinja2 fragments

### Frontend Changes

- `dashboard/templates/docs_detail.html` — Add IDE tab nav item; add `#ide-panel` div target
- `dashboard/templates/fragments/docs_ide_tab.html` — New fragment
- `dashboard/templates/fragments/docs_guide_type_editor.html` — New fragment
- `dashboard/templates/fragments/docs_guide_instance_editor.html` — New fragment
- `dashboard/templates/fragments/docs_guide_sections_panel.html` — New fragment
- `dashboard/templates/fragments/docs_section_diff_panel.html` — New fragment

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00041/F-00041_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00041/workflow-manifest.json` | Manifest | Orchestrator step definitions |
| `ai-dev/active/F-00041/prompts/F-00041_S01_Frontend_prompt.md` | Prompt | Endpoints + templates |
| `ai-dev/active/F-00041/prompts/F-00041_S02_CodeReview_Frontend_prompt.md` | Prompt | Review S01 |
| `ai-dev/active/F-00041/prompts/F-00041_S03_Tests_prompt.md` | Prompt | Integration tests |
| `ai-dev/active/F-00041/prompts/F-00041_S04_CodeReview_Final_prompt.md` | Prompt | Global review |
| `ai-dev/active/F-00041/prompts/F-00041_S09_QVBrowser_prompt.md` | Prompt | Playwright browser verification |

## Acceptance Criteria

### AC1: IDE tab loads on document detail page

```
Given a document detail page at /project/{id}/docs/{doc_id}
When the user clicks the "IDE" tab
Then the IDE panel loads via htmx with guide editor and diff viewer sections visible
```

### AC2: Type guide editor shows and saves content

```
Given a type guide exists for the document's doc_type
When the IDE tab is open
Then the type guide textarea is pre-populated with the guide content
And when the user edits and clicks Save, POST /guide/type is called
And the textarea reflects the saved content (htmx swap)
```

### AC3: Instance guide shows "inheriting" message when no override exists

```
Given no instance guide exists for the document
When the IDE tab instance guide panel is loaded
Then the textarea is empty and a message "Inheriting from type guide" is shown
```

### AC4: Section guide panel lists sections from doc content

```
Given a document with content containing H2 headings "## Purpose" and "## Architecture"
When the sections guide panel is loaded
Then two sections appear: "Purpose" and "Architecture", each with an editable textarea
```

### AC5: Section diff panel shows changed sections

```
Given two document versions where "Purpose" changed and "Architecture" is identical
When the section diff panel is loaded with v1 and v2
Then "Purpose" section shows as "changed" with unified diff content
And "Architecture" section shows as "unchanged" badge
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Doc with no H2 headings | Plain prose content | Sections panel shows single "Document" guide section |
| Save empty guide | Textarea cleared and saved | Upsert with empty string — valid (empty guide clears guidance) |
| Delete instance guide (none exists) | DELETE when no instance guide | Returns 204 (idempotent) |
| Type guide save fails | DB error | Returns 500 with error toast; no partial save |
| IDE tab load with no guides at any level | No type, instance, or section guides | All editors empty; no error; placeholder text shown |
| Section name with special characters | `section_name = "API & Changelog"` | URL-encoded in htmx requests; decoded in router |

## Invariants

1. Saving a guide via the IDE tab uses the same `DocService` methods as any other caller — no direct DB access in routers
2. The IDE tab is lazy-loaded only on user click — no IDE content is rendered on initial page load
3. Existing tabs (Overview, HTML View, PDF View, Versions, Diff) are unchanged
4. The section guide panel derives section names from the document's current content at render time via `extract_sections` — not from a stored list

## Dependencies

### Batch Execution Context

This feature is part of a batch containing **F-00037 → F-00038 + F-00039 → F-00040 → F-00041**. F-00041 is the top of the chain and runs last.

### Execution Wave

**Wave 4** — starts only after F-00037, F-00038, F-00039, and F-00040 are all merged into main.

### Inbound Dependencies (what this feature needs)

Everything this feature uses must already exist in main when the F-00041 worktree is created.

| Dependency | Artifact needed | Where used in F-00041 |
|------------|----------------|----------------------|
| **F-00037** (Wave 1) | `DocService.get_type_guide(doc_type)` | Type guide GET endpoint (`GET /guide/type`) reads and returns the guide content to the editor textarea |
| **F-00037** | `DocService.save_type_guide(doc_type, guide_md)` | Type guide POST endpoint (`POST /guide/type`) persists the edited content |
| **F-00038** (Wave 2) | `DocService.get_instance_guide(project_id, doc_id)` | Instance guide GET endpoint |
| **F-00038** | `DocService.save_instance_guide(project_id, doc_id, guide_md)` | Instance guide POST endpoint |
| **F-00038** | `DocService.delete_instance_guide(project_id, doc_id)` | Instance guide DELETE endpoint |
| **F-00038** | `DocService._effective_guide(project_id, doc_id, doc_type)` | Merged guide preview panel — shows what the AI will actually receive |
| **F-00039** (Wave 2) | `DocService.list_section_guides(project_id, doc_id)` | Section guides panel — populates the list of editable sections |
| **F-00039** | `DocService.get_section_guide(project_id, doc_id, section_name)` | Per-section guide GET endpoint |
| **F-00039** | `DocService.save_section_guide(project_id, doc_id, section_name, guide_md)` | Per-section guide POST endpoint |
| **F-00039** | `DocService.delete_section_guide(project_id, doc_id, section_name)` | Per-section guide DELETE endpoint |
| **F-00039** | `orch.doc_sections.extract_sections(content: str) -> list[str]` | Section guide panel renders one editable textarea per section; sections are extracted from `doc.content` at render time — **import from `orch.doc_sections`, do not re-implement** |
| **F-00040** (Wave 3) | `GET /api/docs/{doc_id}/diff/sections?v1=N&v2=N` (JSON) | Section diff panel fetches this via htmx on load; displays section-level change summary |
| **F-00040** | `GET /api/docs/{doc_id}/diff/sections/{section_name}?v1=N&v2=N` (HTML) | Per-section diff detail, loaded via htmx when user expands a section in the diff panel |
| **F-00040** | `GET /api/docs/{doc_id}/diff/ai-summary?v1=N&v2=N` (204 stub) | "AI Summary" button in diff panel; 204 response → show "coming soon" badge |

### Outbound Dependencies

**Blocks**: None — F-00041 is the terminal feature in this batch. It delivers the user-facing surface for all backend work done in F-00037 through F-00040.

**Future feature F-00025** (AI-powered diff summarization) will change the `/diff/ai-summary` endpoint from 204 to a real response. The F-00041 UI must handle both gracefully: show "coming soon" on 204, show AI summary content on 200. No changes to F-00041 templates will be needed when F-00025 ships if the 204 branch is properly implemented.

## TDD Approach

- Integration tests: test all 9 htmx endpoints with real DB via testcontainer
  - GET endpoints return HTML 200 with expected content markers (section headings, textarea elements)
  - POST endpoints persist changes (verify via GET round-trip)
  - DELETE endpoints return 200/204 and subsequent GET shows "inheriting" state
- Browser verification (Playwright):
  - Open docs detail page, click IDE tab, assert panel visible
  - Edit type guide textarea, click Save, assert content updated in DOM
  - Verify section list renders with correct section names from doc content

## Notes

The htmx pattern follows existing dashboard conventions: POST returns the updated fragment HTML
(not a redirect), the fragment swaps in-place via `hx-target`/`hx-swap="innerHTML"`. Toast
messages use the existing `fragments/toast_message.html` pattern from other routes.

Section names in URL paths use percent-encoding (`urllib.parse.quote`/`unquote`) for special
characters. FastAPI's path parameter will auto-decode them. Agents must verify that section
names containing `/` or `&` are handled correctly.

The section diff panel queries the new `/diff/sections` endpoint from F-00040. If no versions
have been created yet for this document, the diff panel shows a "No versions to compare" message
rather than an error.
