# F-00045_S01_Database_report.md

## Step S01 — Database Implementation (CodeIndexJob ORM + Migration)

**Work Item**: F-00045 — Code Understanding: Foundation  
**Agent**: database-impl  
**Step**: S01  
**Date**: 2026-04-15

---

## What Was Done

### 1. ORM Model: `CodeIndexJob` (`orch/db/models.py`)

Appended the `CodeIndexJob` class using SQLAlchemy 2.0 `Mapped[]` declarative style, following existing conventions. Uses the module-level `_TIMESTAMPTZ` alias (already defined) and `Any` (already imported from `typing`). No existing model was modified.

**Table**: `code_index_jobs`  
**Columns**: id, project_id, status, provider, llm_model, embed_model, index_tier, files_discovered, files_indexed, chunks_created, languages_detected (JSONB), errors (JSONB), doc_id, triggered_at, completed_at, created_at, updated_at  
**Indexes**: `idx_code_index_jobs_project_id`, `idx_code_index_jobs_status`  
**FK Constraints**: `projects(id)` ON DELETE CASCADE, `project_docs(id)` ON DELETE SET NULL

### 2. Alembic Migration (`orch/db/migrations/versions/b9f2c7a1e8d4_add_code_index_jobs.py`)

Revision ID `b9f2c7a1e8d4`, chains from `add_doc_instance_guides` (confirmed as current head via `uv run alembic heads`). Uses `sa.Text()` for string columns, `sa.Integer()` for integer columns, `JSONB()` from `sqlalchemy.dialects.postgresql` for JSONB columns, and `sa.DateTime(timezone=True)` for timestamp columns.

### 3. Integration Tests (`tests/integration/test_code_index_job.py`)

7 test cases covering:
- `test_create_code_index_job_defaults` — minimal insert, all defaults
- `test_create_code_index_job_all_fields` — all fields populated including ProjectDoc FK
- `test_code_index_job_status_transitions` — queued → running → completed
- `test_code_index_job_fk_invalid_project` — FK violation on missing project
- `test_code_index_job_doc_id_null` — nullable doc_id
- `test_code_index_job_languages_detected_jsonb` — JSONB list round-trip
- `test_code_index_job_errors_jsonb` — JSONB dict list round-trip

All tests use `db_session` fixture (testcontainer, never live DB) and `test_project` fixture.

---

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Appended `CodeIndexJob` model |
| `orch/db/migrations/versions/b9f2c7a1e8d4_add_code_index_jobs.py` | New migration (chained from `add_doc_instance_guides`) |
| `tests/integration/test_code_index_job.py` | New test file (7 test cases) |

---

## Test Results

```
uv run pytest tests/integration/test_code_index_job.py -v
→ 7 passed, 1 warning (SAWarning about transaction rollback — unrelated to this model)
```

```
uv run ruff check ... (models.py, migration, test file)
→ All checks passed!
```

```
uv run mypy orch/db/models.py
→ Success: no issues found
```

---

## Notes

- The `MigrationLock` table is declared in `models.py` and included in `Base.metadata.create_all()` during test setup, so it exists in the test DB. This is fine — it's a valid table.
- `completed_at` in tests uses `datetime.now(UTC).replace(tzinfo=None)` to get a naive datetime matching the TIMESTAMPTZ behavior (store as UTC, let PostgreSQL handle timezone).
- TDD was followed: tests were written first (RED phase), then model and migration were added (GREEN phase), then lint/ruff issues were fixed (REFACTOR phase).