# F-00038: Instance Guide Overlay

**Type**: Feature
**Phase**: Interactive Document IDE — Foundation Layer
**Priority**: High
**Created**: 2026-04-13
**Status**: Draft
**Repository**: `iw-ai-core`

---

## Description

Adds a per-document instance guide that overlays the type-level guide (from F-00037).
When a generation job runs, the effective guide is the merged result of the type guide
(`doc_type_guides`) and any instance-specific override stored in a new `doc_instance_guides`
table (keyed by `project_doc.id`). The merged guide is snapshotted into
`doc_generation_jobs.guide_snapshot`, replacing the snapshot logic added by F-00037.

## Architecture References

| File | Relevance |
|------|-----------|
| `orch/db/models.py:912` | `DocGenerationJob.guide_snapshot` — added by F-00037 |
| `orch/db/models.py:816` | `ProjectDoc` — the doc whose instance guide we store |
| `orch/doc_service.py:449` | `DocService.create_doc_job()` — snapshot logic to update |
| `ai-dev/active/F-00037/F-00037_Feature_Design.md` | Type-guide layer this overlays |

## Scope

### In Scope

- New `doc_instance_guides` table: `doc_id` (TEXT PK, FK to `project_docs.id`), `guide_md` (TEXT NOT NULL), `updated_at` (TIMESTAMPTZ)
- Alembic migration creating the table
- New `DocInstanceGuide` SQLAlchemy model in `orch/db/models.py`
- `DocService` methods: `get_instance_guide(project_id, doc_id)`, `save_instance_guide(project_id, doc_id, guide_md)`, `delete_instance_guide(project_id, doc_id)`
- `DocService._effective_guide(project_id, doc_id, doc_type)` — merge logic: instance guide (if present) overrides type guide; falls back to type guide if no instance override; falls back to empty string if neither exists
- `DocService.create_doc_job()` updated to call `_effective_guide()` instead of `get_type_guide()` for snapshot
- Unit tests: merge logic (instance overrides type, fallback chain), CRUD methods
- Integration tests: end-to-end — type guide only, instance override, snapshot reflects effective guide

### Out of Scope

- Section-level guide (F-00039)
- UI for editing instance guides (F-00041)
- Guide merge conflict resolution (simple override: instance wins entirely)

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Database | Migration: `doc_instance_guides` table | — |
| S02 | Backend | `DocInstanceGuide` model; `DocService` CRUD + `_effective_guide`; update `create_doc_job` | S01 complete |
| S03 | CodeReview_Backend | Review S02 | — |
| S04 | Tests | Unit + integration tests for overlay logic | S03 complete |
| S05 | CodeReview_Final | Global review | S04 complete |
| S06 | QV: lint | `ruff check orch/ tests/` | — |
| S07 | QV: format | `ruff format --check orch/ tests/` | — |
| S08 | QV: typecheck | `mypy orch/db/models.py orch/doc_service.py` | — |
| S09 | QV: unit-tests | `pytest tests/unit/ -x -q` | — |
| S10 | QV: integration-tests | `pytest tests/integration/ -x -q` | — |

### Database Changes

- **New tables**: `doc_instance_guides`
- **Modified tables**: None (snapshot logic changes but no schema change — `guide_snapshot` column already added by F-00037)
- **New indexes**: `idx_doc_instance_guides_doc_id` on `doc_id` (implicit from PK)
- **Migration notes**: Table created with FK to `project_docs.id` ON DELETE CASCADE; nullable — docs without an instance override just use the type guide

### API Changes

- None in this feature — guide access via `DocService`; API endpoints deferred to F-00041

### Frontend Changes

- None in this feature

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00038/F-00038_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00038/workflow-manifest.json` | Manifest | Orchestrator step definitions |
| `ai-dev/active/F-00038/prompts/F-00038_S01_Database_prompt.md` | Prompt | Migration |
| `ai-dev/active/F-00038/prompts/F-00038_S02_Backend_prompt.md` | Prompt | Model + service |
| `ai-dev/active/F-00038/prompts/F-00038_S03_CodeReview_Backend_prompt.md` | Prompt | Review S02 |
| `ai-dev/active/F-00038/prompts/F-00038_S04_Tests_prompt.md` | Prompt | Tests |
| `ai-dev/active/F-00038/prompts/F-00038_S05_CodeReview_Final_prompt.md` | Prompt | Global review |

## Acceptance Criteria

### AC1: Instance guide overrides type guide in snapshot

```
Given a type guide exists for 'technical' and an instance guide exists for doc 'arch-overview'
When a generation job is created for 'arch-overview'
Then doc_generation_jobs.guide_snapshot contains the instance guide content, not the type guide
```

### AC2: Falls back to type guide when no instance override

```
Given a type guide exists for 'functional' and no instance guide exists for doc 'overview'
When a generation job is created for 'overview'
Then doc_generation_jobs.guide_snapshot contains the type guide content
```

### AC3: Falls back to empty string when neither guide exists

```
Given no type guide exists for 'unknown_type' and no instance guide for doc 'x'
When a generation job is created for doc 'x' of type 'unknown_type'
Then doc_generation_jobs.guide_snapshot is None or empty string (no exception raised)
```

### AC4: Instance guide CRUD round-trip

```
Given doc 'my-doc' has no instance guide
When save_instance_guide('proj', 'my-doc', '## My Guide\n...')
Then get_instance_guide('proj', 'my-doc') returns '## My Guide\n...'
And delete_instance_guide('proj', 'my-doc') removes the row
And get_instance_guide('proj', 'my-doc') returns None
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| No instance guide, no type guide | Doc with unknown doc_type | `guide_snapshot = None` in job |
| Instance guide exists, no type guide | Instance override only | Snapshot = instance content |
| Type guide exists, no instance | Type guide only | Snapshot = type guide content |
| Instance guide overrides type | Both exist | Snapshot = instance content (instance wins) |
| Delete instance guide | Guide row deleted | Falls back to type guide on next job |
| FK violation | `save_instance_guide` for non-existent doc | Raises DB integrity error (let propagate) |

## Invariants

1. `doc_instance_guides.doc_id` is PRIMARY KEY — one override per document maximum
2. `guide_snapshot` in `doc_generation_jobs` always reflects the effective guide at job creation time; updating guides later does not retroactively change historical snapshots
3. `_effective_guide()` never raises — returns `None` when no guide exists at either level
4. `doc_instance_guides.updated_at` is always set on INSERT and UPDATE

## Dependencies

### Batch Execution Context

This feature is part of a batch containing **F-00037 → F-00038 + F-00039 → F-00040 → F-00041**. F-00038 runs in Wave 2, in parallel with F-00039, after F-00037 is fully merged.

### Execution Wave

**Wave 2** — starts only after F-00037 is merged into main. Runs in parallel with F-00039 (no shared files between them).

### Inbound Dependencies (what this feature needs)

| Dependency | What is needed | Why |
|------------|---------------|-----|
| **F-00037** (Wave 1, same batch) | `doc_type_guides` table must exist | The `_effective_guide()` method calls `DocService.get_type_guide()` to fetch the type-level fallback |
| **F-00037** | `DocTypeGuide` model in `orch/db/models.py` | Imported and used in service layer |
| **F-00037** | `guide_snapshot TEXT` column on `doc_generation_jobs` | The snapshot logic in `create_doc_job()` already writes to this column; F-00038 replaces the write with the merged effective guide instead of just the type guide |
| **F-00037** | Seeded rows in `doc_type_guides` | Integration tests exercise the fallback path: no instance guide → snapshot = type guide content |
| **F-00037** | Alembic HEAD migration | The migration for `doc_instance_guides` must set `down_revision` to F-00037's migration revision |

### Outbound Dependencies (what this feature provides to the batch)

| Artifact | Used by |
|----------|---------|
| `doc_instance_guides` table (columns: `doc_id TEXT PK FK→project_docs.id ON DELETE CASCADE`, `guide_md TEXT`, `updated_at TIMESTAMPTZ`) | F-00041 (instance guide editor Save/Delete buttons call service methods backed by this table) |
| `DocInstanceGuide` SQLAlchemy model in `orch/db/models.py` | F-00041 (routers import model for type annotations) |
| `DocService.get_instance_guide(project_id, doc_id) -> str | None` | F-00041 (instance guide GET endpoint) |
| `DocService.save_instance_guide(project_id, doc_id, guide_md)` | F-00041 (instance guide POST endpoint) |
| `DocService.delete_instance_guide(project_id, doc_id)` | F-00041 (instance guide DELETE endpoint) |
| `DocService._effective_guide(project_id, doc_id, doc_type) -> str | None` | F-00041 (merged guide preview panel in the IDE tab) |
| Updated `create_doc_job()` — snapshots effective (merged) guide instead of type-only guide | F-00041 (no direct call, but users see the merged guide reflected in job history) |

## TDD Approach

- Unit tests: `_effective_guide` merge logic with stub session — test all three fallback scenarios (instance wins, type fallback, neither)
- Unit tests: `get_instance_guide` / `save_instance_guide` / `delete_instance_guide` with stub session
- Integration tests: full DB round-trip with real testcontainer — seed type guide, create instance guide, create job, verify `guide_snapshot` value

## Notes

The override is intentionally coarse-grained (instance replaces type, not patches it). This is
consistent with Exstream's concept of package-level overrides. Fine-grained section merging is
addressed by F-00039 at the section level, not at the instance guide level.

ON DELETE CASCADE on the FK ensures removing a doc also removes its instance guide, preventing orphaned rows.
