# F-00040: Enhanced Document Diff

**Type**: Feature
**Phase**: Interactive Document IDE — Foundation Layer
**Priority**: High
**Created**: 2026-04-13
**Status**: Draft
**Repository**: `iw-ai-core`

---

## Description

Introduces a new `orch/doc_diff.py` module that provides section-aware document diffing using H2
headings as section boundaries. Three new diff endpoints replace the simple unified-diff view
(`/api/docs/{doc_id}/diff`) with richer structured output: a section-level change summary, a
section-by-section unified diff, and a placeholder AI-summary endpoint that gracefully returns
HTTP 204 until F-00025 (AI-powered diff summarization) ships. The original `DocService.diff_versions()`
method is retained for backward compatibility but new callers route through `doc_diff.py`.

## Architecture References

| File | Relevance |
|------|-----------|
| `orch/doc_service.py:562` | `DocService.diff_versions()` — retained as-is for backward compat |
| `dashboard/routers/docs.py:641` | Existing `/api/docs/{doc_id}/diff` endpoint — superseded by new routes |
| `orch/doc_sections.py` | `extract_sections` / `split_by_sections` — added by F-00039; required |
| `orch/db/models.py:888` | `ProjectDocVersion` — version records queried for diff |
| `ai-dev/active/F-00039/F-00039_Feature_Design.md` | `orch/doc_sections.py` module this depends on |

## Scope

### In Scope

- New module `orch/doc_diff.py` with:
  - `SectionDiff` dataclass: `section_name: str`, `status: Literal["added", "removed", "changed", "unchanged"]`, `unified_diff: list[str]`
  - `DocDiff` dataclass: `version_old: int`, `version_new: int`, `sections: list[SectionDiff]`
  - `diff_document_versions(old_content: str, new_content: str, version_old: int, version_new: int) -> DocDiff` — splits both versions by H2 sections, diffs each section pair, classifies status
  - Documents with no H2 headings treated as one section named `"Document"` (using `extract_sections` from `orch/doc_sections.py`)

- Three new dashboard routes added to `dashboard/routers/docs.py`:
  - `GET /api/docs/{doc_id}/diff/sections?v1=N&v2=N` — returns `DocDiff` as JSON (structured section summary)
  - `GET /api/docs/{doc_id}/diff/sections/{section_name}?v1=N&v2=N` — returns unified diff for a single named section (HTMLResponse with pre-rendered diff)
  - `GET /api/docs/{doc_id}/diff/ai-summary?v1=N&v2=N` — returns HTTP 204 with header `X-Stub: waiting-for-F-00025` until F-00025 ships; no blocking error

- Existing `/api/docs/{doc_id}/diff` route **preserved** — still calls `DocService.diff_versions()` (unified diff of whole document); no change to its behavior

- Unit tests for `doc_diff.py`: section pairing, status classification (added/removed/changed/unchanged), no-H2 fallback
- Integration tests: three new endpoints with real DB (two versions, verify section summary, verify per-section diff, verify AI-summary returns 204)

### Out of Scope

- AI-powered diff summarization (F-00025)
- Frontend diff viewer UI (F-00041)
- Diffing section guides (only document content versions are diffed)
- Removing or modifying the existing `/api/docs/{doc_id}/diff` endpoint

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | `orch/doc_diff.py` module; three new routes in `dashboard/routers/docs.py` | — |
| S02 | CodeReview_Backend | Review S01 | — |
| S03 | Tests | Unit tests for `doc_diff.py`; integration tests for new endpoints | S02 complete |
| S04 | CodeReview_Final | Global review | S03 complete |
| S05 | QV: lint | `ruff check orch/ dashboard/ tests/` | — |
| S06 | QV: format | `ruff format --check orch/ dashboard/ tests/` | — |
| S07 | QV: typecheck | `mypy orch/doc_diff.py dashboard/routers/docs.py` | — |
| S08 | QV: unit-tests | `pytest tests/unit/ -x -q` | — |
| S09 | QV: integration-tests | `pytest tests/integration/ -x -q` | — |

### Database Changes

- **None** — diff is computed in-memory from `ProjectDocVersion.content`; no new tables or columns

### API Changes

- **New endpoints**:
  - `GET /project/{project_id}/api/docs/{doc_id}/diff/sections` — section-level summary JSON
  - `GET /project/{project_id}/api/docs/{doc_id}/diff/sections/{section_name}` — per-section unified diff HTML
  - `GET /project/{project_id}/api/docs/{doc_id}/diff/ai-summary` — stub (204) until F-00025
- **Unchanged endpoints**: `GET /project/{project_id}/api/docs/{doc_id}/diff` — existing whole-doc diff

### Frontend Changes

- None in this feature — new endpoints are consumed by F-00041 IDE UI

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00040/F-00040_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00040/workflow-manifest.json` | Manifest | Orchestrator step definitions |
| `ai-dev/active/F-00040/prompts/F-00040_S01_Backend_prompt.md` | Prompt | Module + routes |
| `ai-dev/active/F-00040/prompts/F-00040_S02_CodeReview_Backend_prompt.md` | Prompt | Review S01 |
| `ai-dev/active/F-00040/prompts/F-00040_S03_Tests_prompt.md` | Prompt | Tests |
| `ai-dev/active/F-00040/prompts/F-00040_S04_CodeReview_Final_prompt.md` | Prompt | Global review |

## Acceptance Criteria

### AC1: Section diff classifies changed sections correctly

```
Given version 1 has sections "Purpose" and "Architecture"
And version 2 has sections "Purpose" (modified) and "Architecture" (identical) and "Usage" (new)
When diff_document_versions(v1_content, v2_content, 1, 2) is called
Then SectionDiff for "Purpose" has status "changed"
And SectionDiff for "Architecture" has status "unchanged"
And SectionDiff for "Usage" has status "added"
```

### AC2: No H2 headings treated as single "Document" section

```
Given version 1 and version 2 both have content with no H2 headings
When diff_document_versions is called
Then DocDiff.sections contains exactly one SectionDiff with section_name="Document"
```

### AC3: GET /api/docs/{doc_id}/diff/sections returns section summary

```
Given doc 'my-doc' has versions v1 and v2 in the database
When GET /api/docs/my-doc/diff/sections?v1=1&v2=2
Then response is 200 JSON with keys "version_old", "version_new", "sections"
And each section entry has "section_name", "status", and "unified_diff"
```

### AC4: GET /api/docs/{doc_id}/diff/ai-summary returns 204

```
Given any two valid doc versions
When GET /api/docs/my-doc/diff/ai-summary?v1=1&v2=2
Then response status is 204
And response header X-Stub = "waiting-for-F-00025"
```

### AC5: Existing diff endpoint unchanged

```
Given the existing /api/docs/{doc_id}/diff endpoint
When GET /api/docs/my-doc/diff?v1=1&v2=2
Then response is identical to pre-F-00040 behavior (HTML unified diff)
And DocService.diff_versions() is still present in doc_service.py
```

### AC6: GET /api/docs/{doc_id}/diff/sections/{section_name} returns per-section diff

```
Given doc 'my-doc' has versions v1 and v2 in the database
And the diff between v1 and v2 contains a section named "Purpose"
When GET /api/docs/my-doc/diff/sections/Purpose?v1=1&v2=2
Then response is 200 HTML containing the unified diff for that section
When GET /api/docs/my-doc/diff/sections/NonExistent?v1=1&v2=2
Then response status is 404 with detail "section not found in diff"
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| v1 == v2 | Same version number | HTTP 422 "v1 must be less than v2" |
| v1 > v2 | Reversed order | HTTP 422 "v1 must be less than v2" |
| Version not found | v1 or v2 doesn't exist | HTTP 404 with detail |
| Doc not found | Invalid doc_id | HTTP 404 with detail |
| No H2 headings | Plain prose document | Single section "Document" with full diff |
| Section added in v2 | Section exists in v2 but not v1 | `status = "added"`, `unified_diff` shows all lines as added |
| Section removed in v2 | Section exists in v1 but not v2 | `status = "removed"`, `unified_diff` shows all lines as removed |
| Section name not found | GET /diff/sections/{name} where name absent in diff | HTTP 404 "section not found in diff" |
| Empty section body | Section header only, no body text | `unified_diff = []`, `status = "unchanged"` (or "added" if only in v2) |

## Invariants

1. `DocService.diff_versions()` is never removed or renamed — backward compatibility is permanent
2. The existing `/api/docs/{doc_id}/diff` endpoint behavior is unchanged
3. The AI-summary endpoint always returns 204 (not 501 or 503) — graceful stub, not an error
4. `diff_document_versions` never raises on valid string inputs — handles edge cases internally
5. `section_name = "Document"` is the canonical fallback when no H2 headings are found

## Dependencies

### Batch Execution Context

This feature is part of a batch containing **F-00037 → F-00038 + F-00039 → F-00040 → F-00041**. F-00040 runs in Wave 3, after both F-00038 and F-00039 are merged.

### Execution Wave

**Wave 3** — starts only after F-00038 and F-00039 are both merged into main (the Alembic multi-head from Wave 2 must be resolved first). Runs alone; F-00041 waits for F-00040.

### Inbound Dependencies (what this feature needs)

| Dependency | What is needed | Why |
|------------|---------------|-----|
| **F-00039** (Wave 2, same batch) | `orch/doc_sections.py` module with `extract_sections(content: str) -> list[str]` and `split_by_sections(content: str) -> dict[str, str]` | `orch/doc_diff.py` imports these two functions directly. Without this module, F-00040 cannot be implemented. Do not re-implement section parsing — import from `orch.doc_sections`. |
| **F-00039** | `doc_section_guides` table and migrations resolved | F-00040 adds no new DB changes, but Alembic HEAD must be a single revision (not multi-head) before any future migration can be added |
| **F-00038** | Merged into main before this wave | No direct code dependency, but the Alembic merge migration (resolving the F-00038 + F-00039 dual heads) must be present in main before F-00040's worktree is created |

### Outbound Dependencies (what this feature provides to the batch)

| Artifact | Used by |
|----------|---------|
| `orch/doc_diff.py` module — `SectionDiff`, `DocDiff` dataclasses, `diff_document_versions(old, new, v_old, v_new) -> DocDiff` | **F-00041** does NOT import `doc_diff.py` directly — the IDE UI calls the HTTP endpoints below |
| `GET /project/{project_id}/api/docs/{doc_id}/diff/sections?v1=N&v2=N` → JSON `DocDiff` | **F-00041** section diff panel fetches this endpoint via htmx to populate the section comparison view |
| `GET /project/{project_id}/api/docs/{doc_id}/diff/sections/{section_name}?v1=N&v2=N` → HTML unified diff | **F-00041** per-section diff detail (htmx partial swap when user expands a section) |
| `GET /project/{project_id}/api/docs/{doc_id}/diff/ai-summary?v1=N&v2=N` → HTTP 204 + `X-Stub: waiting-for-F-00025` | **F-00041** AI summary button in the IDE tab (shows "coming soon" state based on 204 response); **F-00025** (future feature replaces this stub with real AI summarization — no interface change needed) |

### What this feature does NOT touch

- `DocService.diff_versions()` — preserved as-is for backward compatibility; the existing `/api/docs/{doc_id}/diff` endpoint continues to call it unchanged
- No database schema changes — `doc_diff.py` is a pure computation module operating on strings only

## TDD Approach

- Unit tests (`tests/unit/test_doc_diff.py`):
  - `test_diff_no_h2_headings` — fallback to "Document" section
  - `test_diff_added_section` — section only in v2
  - `test_diff_removed_section` — section only in v1
  - `test_diff_changed_section` — section modified between versions
  - `test_diff_unchanged_section` — identical section content
  - `test_diff_multiple_sections` — realistic doc with 3+ sections
- Integration tests (`tests/integration/api/test_docs_diff_api.py`):
  - `test_sections_endpoint_returns_json` — valid versions → 200 JSON
  - `test_sections_single_section_endpoint` — per-section diff HTML
  - `test_ai_summary_returns_204` — stub endpoint
  - `test_v1_gte_v2_returns_422` — validation error
  - `test_missing_version_returns_404` — version not found

## Notes

The module `orch/doc_diff.py` is intentionally separate from `orch/doc_service.py` to keep
`DocService` focused on CRUD and orchestration. `doc_diff.py` is a pure computation module
with no database dependencies — it operates on strings only and is fully unit-testable without
a database fixture.

The 204 response for `/diff/ai-summary` uses a response header `X-Stub: waiting-for-F-00025`
so API consumers can distinguish a deliberate stub from an empty response. No body is returned.
When F-00025 ships, it replaces this stub with a real implementation; no interface change is
needed at the caller side (204 → 200 with JSON body).
