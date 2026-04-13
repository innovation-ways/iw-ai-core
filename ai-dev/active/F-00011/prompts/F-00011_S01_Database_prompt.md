# F-00011_S01_Database_prompt

**Work Item**: F-00011 — Project-Level Documentation System — Foundation (Phase 1)
**Step**: S01
**Agent**: Database

---

## Input Files

- `ai-dev/active/F-00011/F-00011_Feature_Design.md` — Design document (read fully before starting)
- `orch/db/models.py` — Existing ORM models and FTS trigger patterns
- `orch/db/migrations/versions/` — Existing migrations for style reference
- `CLAUDE.md` — Project-specific rules (critical — read before writing any code)

## Output Files

- `orch/db/models.py` — Extended with three new models
- `orch/db/migrations/versions/{timestamp}_add_project_docs_tables.py` — Alembic migration
- `ai-dev/work/F-00011/reports/F-00011_S01_Database_report.md` — Step report

## Context

You are implementing the database layer for **F-00011: Project-Level Documentation System**.

This step adds three new SQLAlchemy models and the corresponding Alembic migration. The design document (Section "Data Models") defines the exact schema — read it thoroughly. The existing `WorkItem` model in `orch/db/models.py` uses the same Tier 1 TEXT + TSVECTOR pattern we are replicating for `ProjectDoc`; use it as the primary reference.

## Requirements

### 1. New PostgreSQL ENUMs

Define four new Python `Enum` classes and corresponding `ENUM` type declarations for the migration:

- `DocType`: `module`, `api`, `architecture`, `release_notes`, `error_catalog`, `webhook_ref`, `user_guide`
- `DocTier`: `fully_automated`, `semi_automated`, `human_authored`
- `EditorialCategory`: `technical`, `functional`, `guide`, `compliance`, `marketing`, `release`
- `DocStatus`: `planned`, `draft`, `published`, `archived`
- `JobStatus`: `queued`, `running`, `completed`, `failed`

Follow the exact pattern of existing ENUMs in `orch/db/models.py` (both the Python enum class and the SQLAlchemy `ENUM` column type with `create_type=False` in migrations).

### 2. ProjectDoc Model

Create the `ProjectDoc` SQLAlchemy model on table `project_docs` with ALL fields specified in the design document (Section "Data Models"). Key points:

- `id` is a `String` PK using the composite pattern `"{project_id}:{doc_id}"` — NOT a UUID
- `project_id` is a FK → `projects.id` with `ondelete="CASCADE"`
- `audience` and `source_paths` are `JSONB` columns storing Python lists
- `content` is a nullable `Text` column (Tier 1 storage)
- `content_search` is a `TSVECTOR` column — named exactly `content_search` (not `metadata` or any reserved SQLAlchemy name); see the existing `design_doc_search` field on `WorkItem` for the exact pattern
- `version` is a non-nullable `Integer` defaulting to 0
- `generated_at` is a nullable `DateTime(timezone=True)`
- `html_path` and `pdf_path` are nullable `String` columns
- Add `__table_args__` with a `UniqueConstraint` on `(project_id, doc_id)` and `Index` on `project_id`

### 3. ProjectDocVersion Model

Create the `ProjectDocVersion` SQLAlchemy model on table `project_doc_versions` with ALL fields from the design document. Key points:

- `id` is a `BigInteger` PK (BIGSERIAL via `autoincrement=True`)
- `doc_id` is a FK → `project_docs.id` with `ondelete="CASCADE"`
- `content` is non-nullable `Text` (snapshot — never null)
- `trigger_reason` is nullable `String`
- `created_at` is non-nullable `DateTime(timezone=True)` with `server_default=func.now()`

### 4. DocGenerationJob Model

Create the `DocGenerationJob` SQLAlchemy model on table `doc_generation_jobs` with ALL fields from the design document. Key points:

- `id` is a `String` PK — use `uuid4()` as Python-side default (same pattern as `Batch.id`)
- `project_id` FK → `projects.id` with `ondelete="CASCADE"`
- `doc_id` FK → `project_docs.id` with `ondelete="SET NULL"` (nullable — job survives doc deletion)
- `status` uses `JobStatus` ENUM, default `JobStatus.queued`
- All timestamp fields are nullable except `created_at`

### 5. FTS Trigger for ProjectDoc

Add `PROJECT_DOCS_FTS_FUNCTION_SQL` and `PROJECT_DOCS_FTS_TRIGGER_SQL` constants to `orch/db/models.py` following the exact pattern of the existing `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` constants.

The trigger must:
- Fire on INSERT or UPDATE of `project_docs`
- Set `content_search = to_tsvector('english', coalesce(NEW.title, '') || ' ' || coalesce(NEW.content, ''))`
- Use function name `update_project_docs_fts()` and trigger name `trg_project_docs_fts`

### 6. Alembic Migration

Generate (or write manually) the Alembic migration that:
1. Creates all five ENUMs (`doc_type`, `doc_tier`, `editorial_category`, `doc_status`, `job_status`)
2. Creates `project_docs` table with all columns, FK, indexes, and unique constraint
3. Creates `project_doc_versions` table
4. Creates `doc_generation_jobs` table
5. Executes `PROJECT_DOCS_FTS_FUNCTION_SQL` and `PROJECT_DOCS_FTS_TRIGGER_SQL` via `op.execute()`
6. In `downgrade()`: drops all triggers, functions, tables, and ENUMs in reverse order

Use `uv run alembic revision --autogenerate -m "add_project_docs_tables"` to generate the skeleton, then inspect and correct it — autogenerate does not handle ENUMs, FTS triggers, or custom indexes perfectly.

**CRITICAL DB rules from CLAUDE.md:**
- NEVER connect to live DB (port 5433) in tests
- NEVER mock the database in integration tests — use testcontainers
- MUST replace psycopg2 URLs: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`
- MUST run `PROJECT_DOCS_FTS_FUNCTION_SQL` + `PROJECT_DOCS_FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in test fixtures

### 7. Update Test Fixtures

In `tests/conftest.py` (or the relevant conftest), add execution of the new FTS SQL constants after `Base.metadata.create_all()`. Follow the existing pattern for `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` exactly.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Key conventions to follow:
- All models use `Mapped[]` type annotations (SQLAlchemy 2.0 style)
- ENUMs: Python class inherits from `str, enum.Enum`; SQLAlchemy type uses `ENUM(MyEnum, name="my_enum", create_type=False)`
- FK columns end in `_id`
- Timestamps: `created_at` and `updated_at` use `server_default=func.now()` and `onupdate=func.now()`

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write failing tests that verify the new models can be created, queried, and that FTS works
2. **GREEN**: Implement models and migration to make tests pass
3. **REFACTOR**: Ensure code is clean and follows conventions

Write tests in `tests/unit/` or `tests/integration/` as appropriate. At minimum:
- `test_project_doc_create`: create a `ProjectDoc` with all required fields, assert it persists
- `test_project_doc_version_create`: create a version snapshot, assert FK and content
- `test_doc_generation_job_create`: create a job, assert status default is `queued`
- `test_project_doc_fts_trigger`: insert a doc with content, query via `content_search @@ plainto_tsquery('english', 'keyword')`, assert result

## Test Verification (NON-NEGOTIABLE)

After implementation:
1. `make test-unit` — all unit tests must pass
2. `make quality` — ruff + mypy must pass with zero errors

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Database",
  "work_item": "F-00011",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/{timestamp}_add_project_docs_tables.py",
    "tests/conftest.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
