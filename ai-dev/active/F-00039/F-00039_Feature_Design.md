# F-00039: Section-Level Guide

**Type**: Feature
**Phase**: Interactive Document IDE — Foundation Layer
**Priority**: Medium
**Created**: 2026-04-13
**Status**: Draft
**Repository**: `iw-ai-core`

---

## Description

Adds editorial guidance at the H2-section level. A new `doc_section_guides` table stores
per-section guidance keyed by `(doc_id, section_name)` where `section_name` is the text of an
H2 heading. A helper module `orch/doc_sections.py` extracts H2 sections from markdown content.
Documents with no H2 headings are treated as a single section named `"Document"`. Section guides
are surfaced to the generation agent as part of the snapshotted guide context in
`DocGenerationJob.guide_snapshot`.

## Architecture References

| File | Relevance |
|------|-----------|
| `orch/db/models.py:912` | `DocGenerationJob.guide_snapshot` — extended with section data |
| `orch/doc_service.py:84` | `DocService` — new section guide CRUD methods added here |
| `orch/db/models.py:816` | `ProjectDoc` — parent doc for section guides |
| `ai-dev/active/F-00037/F-00037_Feature_Design.md` | Type guide layer (this is one level below) |
| `ai-dev/active/F-00038/F-00038_Feature_Design.md` | Instance guide layer (this complements it) |

## Scope

### In Scope

- New `doc_section_guides` table: `id` (BIGSERIAL PK), `doc_id` (TEXT, FK to `project_docs.id`), `section_name` (TEXT NOT NULL), `guide_md` (TEXT NOT NULL), `updated_at` (TIMESTAMPTZ)
- Unique constraint on `(doc_id, section_name)`
- Alembic migration creating the table
- New `DocSectionGuide` SQLAlchemy model in `orch/db/models.py`
- New `orch/doc_sections.py` module with:
  - `extract_sections(content: str) -> list[str]` — parses H2 headings (`## Heading`); returns `["Document"]` if no H2 headings found
  - `split_by_sections(content: str) -> dict[str, str]` — maps section name to section body text (from one H2 to the next)
- `DocService` methods:
  - `get_section_guide(project_id, doc_id, section_name) -> str | None`
  - `save_section_guide(project_id, doc_id, section_name, guide_md) -> None` (upsert)
  - `delete_section_guide(project_id, doc_id, section_name) -> bool`
  - `list_section_guides(project_id, doc_id) -> list[DocSectionGuide]`
- `DocService.create_doc_job()` updated to snapshot section guides alongside the effective instance/type guide (section guides appended as a structured dict in `guide_snapshot` JSON or as a separate `section_guides_snapshot` JSONB column — see Notes)
- Unit tests: `extract_sections` (with H2s, without H2s, mixed heading levels), section guide CRUD
- Integration tests: upsert round-trip, list returns all section guides, snapshot includes section data

### Out of Scope

- UI for editing section guides (F-00041)
- Section-aware diff using section boundaries (F-00040)
- AI-powered section suggestions

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Database | Migration: `doc_section_guides` table | — |
| S02 | Backend | `DocSectionGuide` model; `orch/doc_sections.py`; `DocService` CRUD + snapshot update | S01 complete |
| S03 | CodeReview_Backend | Review S02 | — |
| S04 | Tests | Unit tests for `extract_sections`; integration tests for guide CRUD and snapshot | S03 complete |
| S05 | CodeReview_Final | Global review | S04 complete |
| S06 | QV: lint | `ruff check orch/ tests/` | — |
| S07 | QV: format | `ruff format --check orch/ tests/` | — |
| S08 | QV: typecheck | `mypy orch/db/models.py orch/doc_service.py orch/doc_sections.py` | — |
| S09 | QV: unit-tests | `pytest tests/unit/ -x -q` | — |
| S10 | QV: integration-tests | `pytest tests/integration/ -x -q` | — |

### Database Changes

- **New tables**: `doc_section_guides`
- **Modified tables**: `doc_generation_jobs` — add `section_guides_snapshot` JSONB column (nullable; NULL for jobs created before this feature; maps section name → guide_md)
- **New indexes**: `idx_doc_section_guides_doc_id` on `doc_id`; unique `uq_doc_section_guides_doc_section` on `(doc_id, section_name)`
- **Migration notes**: `section_guides_snapshot` is nullable — historical jobs have NULL; new jobs include all section guides at creation time

### API Changes

- None — guide access via `DocService`; API endpoints deferred to F-00041

### Frontend Changes

- None in this feature

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00039/F-00039_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00039/workflow-manifest.json` | Manifest | Orchestrator step definitions |
| `ai-dev/active/F-00039/prompts/F-00039_S01_Database_prompt.md` | Prompt | Migration |
| `ai-dev/active/F-00039/prompts/F-00039_S02_Backend_prompt.md` | Prompt | Model + module + service |
| `ai-dev/active/F-00039/prompts/F-00039_S03_CodeReview_Backend_prompt.md` | Prompt | Review S02 |
| `ai-dev/active/F-00039/prompts/F-00039_S04_Tests_prompt.md` | Prompt | Tests |
| `ai-dev/active/F-00039/prompts/F-00039_S05_CodeReview_Final_prompt.md` | Prompt | Global review |

## Acceptance Criteria

### AC1: extract_sections returns section names from H2 headings

```
Given markdown content with headings "## Purpose", "## Architecture", "## Usage"
When extract_sections(content) is called
Then returns ["Purpose", "Architecture", "Usage"]
```

### AC2: extract_sections returns ["Document"] when no H2 headings

```
Given markdown content with only H1 and H3 headings (no H2)
When extract_sections(content) is called
Then returns ["Document"]
```

### AC3: Section guide upsert and retrieval

```
Given doc 'my-doc' with no section guides
When save_section_guide('proj', 'my-doc', 'Purpose', '## Purpose Guide\n...')
Then get_section_guide('proj', 'my-doc', 'Purpose') returns '## Purpose Guide\n...'
And list_section_guides('proj', 'my-doc') returns a list with one entry
```

### AC4: Section guide snapshot captured at job creation

```
Given doc 'my-doc' has section guide for 'Purpose' and 'Architecture'
When a generation job is created for 'my-doc'
Then doc_generation_jobs.section_guides_snapshot = {"Purpose": "...", "Architecture": "..."}
```

### AC5: No H2 headings — snapshot uses "Document" key

```
Given doc 'my-doc' has a section guide for section_name="Document"
When a generation job is created for 'my-doc'
Then section_guides_snapshot = {"Document": "..."}
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| No H2 headings in content | Plain markdown without `##` | `extract_sections` returns `["Document"]` |
| H3 but no H2 | Only `###` headings | `extract_sections` returns `["Document"]` |
| H2 with inline code | `## \`code\` Section` | Returns section name with backticks preserved as-is (verbatim H2 text after `## `, stripped of leading/trailing whitespace only) |
| Empty content | `""` | `extract_sections` returns `["Document"]` |
| No section guides for doc | `list_section_guides` on doc with none | Returns empty list |
| Delete non-existent section | `delete_section_guide` for missing row | Returns `False` (no error) |
| Upsert updates existing | `save_section_guide` called twice | Second call updates `guide_md` and `updated_at` |

## Invariants

1. `(doc_id, section_name)` unique — one guide row per doc+section pair
2. `extract_sections` never raises — empty content returns `["Document"]`
3. `section_guides_snapshot` is immutable after job creation — updating section guides does not affect historical jobs
4. `doc_section_guides.updated_at` always set on INSERT and UPDATE
5. Deleting a `ProjectDoc` cascades to delete all its `DocSectionGuide` rows

## Dependencies

### Batch Execution Context

This feature is part of a batch containing **F-00037 → F-00038 + F-00039 → F-00040 → F-00041**. F-00039 runs in Wave 2, in parallel with F-00038, after F-00037 is fully merged.

### Execution Wave

**Wave 2** — starts only after F-00037 is merged into main. Runs in parallel with F-00038 (the two features touch different tables and different service methods; no file conflicts).

### Inbound Dependencies (what this feature needs)

| Dependency | What is needed | Why |
|------------|---------------|-----|
| **F-00037** (Wave 1, same batch) | `guide_snapshot TEXT` column on `doc_generation_jobs` | F-00039 adds a second snapshot column `section_guides_snapshot JSONB` in the same migration family; the column from F-00037 must already exist so the Alembic revision chain is correct |
| **F-00037** | Alembic HEAD migration | The migration for `doc_section_guides` and `section_guides_snapshot` sets `down_revision` to F-00037's migration (not F-00038's, since Wave 2 is parallel — check `alembic heads` after F-00037 merges) |
| **F-00037** | `DocService.create_doc_job()` updated in F-00037 | F-00039 further modifies `create_doc_job()` to also populate `section_guides_snapshot`; the F-00037 version of this method is the starting point |

### Outbound Dependencies (what this feature provides to the batch)

| Artifact | Used by |
|----------|---------|
| `doc_section_guides` table (columns: `id BIGSERIAL PK`, `doc_id TEXT FK→project_docs.id ON DELETE CASCADE`, `section_name TEXT`, `guide_md TEXT`, `updated_at TIMESTAMPTZ`; unique on `(doc_id, section_name)`) | F-00041 (section guide panel Save/Delete per section) |
| `DocSectionGuide` SQLAlchemy model in `orch/db/models.py` | F-00041 (routers import for type annotations) |
| `section_guides_snapshot JSONB` column on `doc_generation_jobs` | F-00041 (job history shows which section guides were active at generation time) |
| **`orch/doc_sections.py`** module — `extract_sections(content: str) -> list[str]` and `split_by_sections(content: str) -> dict[str, str]` | **F-00040** (critical — `doc_diff.py` imports `extract_sections` and `split_by_sections` directly from this module to split documents into sections for comparison); **F-00041** (section guide panel calls `extract_sections(doc.content)` at render time to populate the section list) |
| `DocService.get_section_guide(project_id, doc_id, section_name) -> str | None` | F-00041 (section guide GET per section) |
| `DocService.save_section_guide(project_id, doc_id, section_name, guide_md)` | F-00041 (section guide POST per section) |
| `DocService.delete_section_guide(project_id, doc_id, section_name) -> bool` | F-00041 (section guide DELETE per section) |
| `DocService.list_section_guides(project_id, doc_id) -> list[DocSectionGuide]` | F-00041 (populate the full section guide panel) |

### Migration Chain Note

Because F-00038 and F-00039 are parallel (Wave 2), their Alembic migrations will both have `down_revision = <F-00037 revision>`. This creates a **multi-head situation** that must be resolved before F-00040 (Wave 3) can add its migration. When the batch executor merges F-00038 and F-00039, it must run `alembic merge heads` to create a merge migration before F-00040 starts. The batch dispatcher handles this automatically via `scripts/worktree_setup.sh`; implementors do not need to resolve this manually.

## TDD Approach

- Unit tests: `extract_sections` — with H2s, without H2s, mixed levels, empty content, H2 with special characters
- Unit tests: `split_by_sections` — verifies correct body text per section
- Unit tests: CRUD methods with stub session (same pattern as F-00037 tests)
- Integration tests: full DB — upsert, retrieve, list, delete, snapshot on job creation

## Notes

Section name extraction strips any trailing `#` characters and strips leading/trailing whitespace.
Inline backticks in section names are preserved as-is in the `section_name` field (the full H2
text after `## ` is used verbatim, normalized to stripped text only).

The `section_guides_snapshot` is stored as JSONB `{"section_name": "guide_md", ...}` — a flat
map of all section guides for the document at job creation time. This is separate from
`guide_snapshot` (which holds the merged type/instance guide from F-00037/F-00038) so the two
guide levels remain distinct and independently queryable.
