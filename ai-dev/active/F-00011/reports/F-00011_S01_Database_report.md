# F-00011_S01_Database_report

**Step**: S01 — Database
**Work Item**: F-00011 — Project-Level Documentation System — Foundation (Phase 1)
**Agent**: Database
**Date**: 2026-04-13

## Summary

Completed the database layer for F-00011: implemented three new SQLAlchemy models (`ProjectDoc`, `ProjectDocVersion`, `DocGenerationJob`), five new PostgreSQL ENUMs, the FTS trigger for full-text search, and the Alembic migration. Added 19 integration tests verifying model creation, FK constraints, cascade deletes, and FTS trigger behavior.

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added 5 ENUMs (DocType, DocTier, EditorialCategory, DocStatus, JobStatus), 3 models (ProjectDoc, ProjectDocVersion, DocGenerationJob), and FTS SQL constants |
| `orch/db/migrations/versions/6a5e03db855a_add_project_docs_tables.py` | New Alembic migration creating 5 ENUMs, 3 tables, indexes, and FTS trigger |
| `tests/integration/conftest.py` | Added PROJECT_DOCS_FTS_* SQL to test fixture setup |
| `tests/integration/test_project_docs.py` | New integration test file with 19 tests |

## Test Results

```
tests/integration/test_project_docs.py: 19 passed
tests/integration/test_models.py: 23 passed
tests/unit/: 576 passed
```

## Quality Checks

- **ruff**: PASSED (no errors)
- **ruff format**: PASSED (all files formatted)
- **mypy** (orch/db/models.py, tests/integration/test_project_docs.py): PASSED

Note: Pre-existing mypy errors in `orch/cli/worktree_commands.py` and `dashboard/routers/worktrees.py` are unrelated to this step's changes.

## Implementation Details

### ENUMs Added
- `DocType`: module, api, architecture, release_notes, error_catalog, webhook_ref, user_guide
- `DocTier`: fully_automated, semi_automated, human_authored
- `EditorialCategory`: technical, functional, guide, compliance, marketing, release
- `DocStatus`: planned, draft, published, archived
- `JobStatus`: queued, running, completed, failed

### Models Implemented
- **ProjectDoc**: Composite PK (`{project_id}:{doc_id}`), JSONB audience/source_paths, TSVECTOR content_search with FTS trigger
- **ProjectDocVersion**: BIGSERIAL PK, FK to ProjectDoc with CASCADE delete, immutable content snapshot
- **DocGenerationJob**: UUID PK, FKs to Project and ProjectDoc (SET NULL on doc deletion), JobStatus enum

### FTS Trigger
- Function: `update_project_docs_fts()`
- Trigger: `trg_project_docs_fts` on INSERT/UPDATE of title, content
- Updates `content_search = to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content,''))`

## Issues/Observations

1. The migration uses raw SQL for the FTS trigger (same pattern as existing `work_items` FTS trigger)
2. The `ProjectDoc.id` is a composite slug string, not a UUID — follows the design spec
3. All tests use testcontainers (never live DB) per CLAUDE.md rules
