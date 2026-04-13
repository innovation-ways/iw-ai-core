# F-00037: Doc-Type Guides — Editable Editorial Guidelines

**Type**: Feature
**Phase**: Interactive Document IDE — Foundation Layer
**Priority**: High
**Created**: 2026-04-13
**Status**: Draft
**Repository**: `iw-ai-core`

---

## Description

Migrates editorial guidelines from static files (`doc-system/editorial/*.md`) into an editable
database table (`doc_type_guides`), one row per `DocType` enum value. Adds a backend service
method to retrieve and save guides, and seeds all existing editorial files as initial rows.
The `DocService.create_doc_job()` method is updated to snapshot the effective guide into a new
`guide_snapshot` column on `doc_generation_jobs`. This is the foundational layer that F-00038
(instance guide overlay) and F-00041 (IDE UI) depend on.

## Architecture References

| File | Relevance |
|------|-----------|
| `orch/db/models.py:151` | `DocType` enum — defines valid `doc_type` values |
| `orch/db/models.py:912` | `DocGenerationJob` — add `guide_snapshot` column |
| `orch/doc_service.py:78` | `DocService` — add guide CRUD methods |
| `orch/db/migrations/versions/20260413160000_add_doc_type_product_overview_feature_catalog.py` | Current HEAD migration (`add_doc_types_functional`) |
| `doc-system/editorial/_default.md` | Default editorial content to seed |
| `doc-system/editorial/marketing.md` | Marketing editorial content to seed |

## Scope

### In Scope

- New `doc_type_guides` table: `doc_type` (TEXT PK), `guide_md` (TEXT NOT NULL), `updated_at` (TIMESTAMPTZ)
- Alembic migration creating the table and seeding rows from `doc-system/editorial/`
- New `DocTypeGuide` SQLAlchemy model in `orch/db/models.py`
- `guide_snapshot` TEXT column on `doc_generation_jobs`
- `DocService` methods: `get_type_guide(doc_type)`, `save_type_guide(doc_type, guide_md)`
- `DocService.create_doc_job()` updated to snapshot the type guide at job creation time
- Unit tests for guide CRUD and snapshot logic
- Integration tests: seed data present, get/save round-trip, snapshot captured in job

### Out of Scope

- Instance guide overlay (F-00038)
- Guide merge logic (F-00038)
- UI for editing guides (F-00041)
- Section-level guide (F-00039)

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Database | Migration: `doc_type_guides` table + seed rows; `guide_snapshot` column on jobs | — |
| S02 | Backend | `DocTypeGuide` model; `DocService.get_type_guide` / `save_type_guide`; update `create_doc_job` to snapshot | — |
| S03 | CodeReview_Backend | Review S02 | — |
| S04 | Tests | Integration tests: seed data, get/save round-trip, snapshot in job | — |
| S05 | CodeReview_Final | Global review | — |
| S06 | QV: lint | `ruff check orch/ tests/` | — |
| S07 | QV: format | `ruff format --check orch/ tests/` | — |
| S08 | QV: typecheck | `mypy orch/db/models.py orch/doc_service.py` | — |
| S09 | QV: unit-tests | `pytest tests/unit/ -x -q` | — |
| S10 | QV: integration-tests | `pytest tests/integration/ -x -q` | — |

### Database Changes

- **New tables**: `doc_type_guides`
- **Modified tables**: `doc_generation_jobs` — add `guide_snapshot TEXT`
- **Migration notes**: Seed `doc_type_guides` from `doc-system/editorial/` files during migration; `guide_snapshot` nullable (NULL for historical jobs created before this feature)

### API Changes

- None in this feature — guide access via `DocService` methods used internally; UI endpoints added in F-00041

### Frontend Changes

- None in this feature

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00037/F-00037_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00037/workflow-manifest.json` | Manifest | Orchestrator step definitions |
| `ai-dev/active/F-00037/prompts/F-00037_S01_Database_prompt.md` | Prompt | Migration |
| `ai-dev/active/F-00037/prompts/F-00037_S02_Backend_prompt.md` | Prompt | Model + service |
| `ai-dev/active/F-00037/prompts/F-00037_S03_CodeReview_Backend_prompt.md` | Prompt | Review S02 |
| `ai-dev/active/F-00037/prompts/F-00037_S04_Tests_prompt.md` | Prompt | Integration tests |
| `ai-dev/active/F-00037/prompts/F-00037_S05_CodeReview_Final_prompt.md` | Prompt | Global review |

## Acceptance Criteria

### AC1: Table and seed data exist after migration

```
Given a fresh database with migrations applied
When I query SELECT COUNT(*) FROM doc_type_guides
Then I get at least 2 rows (one for _default, one for marketing)
```

### AC2: Get and save round-trip

```
Given the database has a row for doc_type='marketing'
When I call DocService.get_type_guide('marketing') and then save_type_guide('marketing', new_content)
Then DocService.get_type_guide('marketing') returns new_content
```

### AC3: Guide snapshot captured at job creation

```
Given a doc_type_guide row exists for 'marketing'
When I create a generation job for a marketing document
Then doc_generation_jobs.guide_snapshot contains the guide_md at creation time
```

### AC4: Unknown doc_type returns None

```
Given no guide row exists for doc_type='nonexistent'
When I call DocService.get_type_guide('nonexistent')
Then None is returned (no exception raised)
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| No guide for doc_type | `get_type_guide('nonexistent')` | Returns `None` |
| Save new guide for unregistered type | `save_type_guide('unknown', '...')` | Upsert succeeds (INSERT) |
| Save updates existing guide | `save_type_guide('marketing', '...')` | Row updated, `updated_at` refreshed |
| Job creation with no guide | doc_type with no guide row | `guide_snapshot = None` |

## Invariants

1. `doc_type_guides.doc_type` is a PRIMARY KEY — no duplicate rows
2. `guide_snapshot` is immutable after job creation — updating the guide does not affect historical jobs
3. `doc_type_guides.updated_at` is always set on INSERT and UPDATE

## Dependencies

### Batch Execution Context

This feature is part of a batch containing **F-00037 → F-00038 + F-00039 → F-00040 → F-00041**. F-00037 is the foundation — it must complete before any other feature in the batch starts.

### Execution Wave

**Wave 1** — runs first; no batch siblings can start until this is merged.

### Inbound Dependencies (what this feature needs)

| Dependency | What is needed | Why |
|------------|---------------|-----|
| **F-00020** (already merged) | `research` value added to `DocType` enum; its migration is the current Alembic HEAD | The new migration in this feature must set `down_revision` to F-00020's migration revision. Run `alembic heads` to confirm before writing the migration. |

### Outbound Dependencies (what this feature provides to the batch)

The following artifacts are created by F-00037 and **must exist** before downstream features run their Database step:

| Artifact | Used by |
|----------|---------|
| `doc_type_guides` table (columns: `doc_type TEXT PK`, `guide_md TEXT`, `updated_at TIMESTAMPTZ`) | F-00038 (reads type guide as fallback in `_effective_guide()`), F-00039 (reads type guide to append to snapshot), F-00041 (UI saves type guide via service) |
| `DocTypeGuide` SQLAlchemy model in `orch/db/models.py` | F-00038 (`_effective_guide` calls `get_type_guide()`), F-00039 (same) |
| `guide_snapshot TEXT` column on `doc_generation_jobs` | F-00038 (extends snapshot logic to include instance guide), F-00039 (adds `section_guides_snapshot` in the same migration) |
| `DocService.get_type_guide(doc_type) -> DocTypeGuide | None` | F-00038, F-00039, F-00041 |
| `DocService.save_type_guide(doc_type, guide_md) -> DocTypeGuide` | F-00041 (type guide editor Save button) |
| Seeded rows in `doc_type_guides` from `doc-system/editorial/` | F-00038 integration tests (require at least one type guide row to test fallback), F-00039 integration tests |

## TDD Approach

- Unit tests: `DocService.get_type_guide` / `save_type_guide` with a mock session
- Integration tests: full DB round-trip — seed data present, get/save, snapshot in job record
- Edge cases: missing guide returns None, upsert on non-existent type

## Notes

The `doc_type_guides` table uses `doc_type TEXT PRIMARY KEY` (not a FK constraint to a PG enum)
for maximum flexibility — a new `DocType` enum value does not require adding a guide row for the
system to function. The `DocService` methods gracefully return `None` when no guide exists.

Guide content is snapshotted at job creation (not at completion) so the exact guide that
instructed the generation is preserved for audit purposes, even if the guide is later updated.
