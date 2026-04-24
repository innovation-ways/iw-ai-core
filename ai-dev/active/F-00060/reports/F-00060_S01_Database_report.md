# F-00060 S01 — Database Report

## What Was Done

**S01** added the `doc_index_jobs` table and `DocIndexJob` ORM class for the hybrid doc Q&A feature (F-00060). This is a structural clone of the existing `code_index_jobs` infrastructure with two renames: `files_discovered` → `items_discovered` and `files_indexed` → `items_indexed`. No FTS, no enums, plain TEXT status.

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `DocIndexJob` ORM class (lines 1373–1419), adjacent to `CodeIndexJob` |
| `orch/db/migrations/versions/74f9b2350784_add_doc_index_jobs.py` | New Alembic migration (structural clone of `b9f2c7a1e8d4_add_code_index_jobs.py`) |
| `tests/integration/test_doc_index_jobs_migration.py` | New integration test (5 cases: table exists, columns/types, indexes, insert with required cols, downgrade/upgrade round-trip) |

## DocIndexJob Schema

Mirrors `code_index_jobs` exactly with two deliberate renames:

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | TEXT PK | NO | `gen_random_uuid()::text` |
| `project_id` | TEXT FK | NO | — |
| `status` | TEXT | NO | `'queued'` |
| `provider` | TEXT | NO | `'local'` |
| `llm_model` | TEXT | YES | — |
| `embed_model` | TEXT | YES | — |
| `index_tier` | TEXT | YES | — |
| `items_discovered` | INT | NO | `0` |
| `items_indexed` | INT | NO | `0` |
| `chunks_created` | INT | NO | `0` |
| `errors` | JSONB | NO | `[]` |
| `triggered_at` | TIMESTAMPTZ | NO | `NOW()` |
| `started_at` | TIMESTAMPTZ | YES | — |
| `completed_at` | TIMESTAMPTZ | YES | — |
| `error_message` | TEXT | YES | — |

Indexes: `idx_doc_index_jobs_project_id`, `idx_doc_index_jobs_status`.

**Deliberate differences from `code_index_jobs`:**
- `items_discovered` / `items_indexed` (vs `files_discovered` / `files_indexed`) — domain-appropriate naming
- `started_at` added (present in `code_index_jobs` as `created_at` only, but spec requires explicit start timestamp)
- No `doc_id` FK (doc index jobs are project-scoped, not tied to a single doc)
- No `languages_detected` JSONB column (irrelevant for doc indexing)
- No `updated_at` column (not needed for doc index jobs; watermark handled at LanceDB layer)

## Test Results

```
tests/integration/test_doc_index_jobs_migration.py::test_table_exists PASSED
tests/integration/test_doc_index_jobs_migration.py::test_columns_and_types PASSED
tests/integration/test_doc_index_jobs_migration.py::test_indexes_exist PASSED
tests/integration/test_doc_index_jobs_migration.py::test_insert_with_required_columns PASSED
tests/integration/test_doc_index_jobs_migration.py::test_downgrade_and_upgrade_round_trip PASSED
========================= 5 passed, 1 warning in 3.88s =========================
```

Full integration suite: **911 passed, 10 skipped** (`make test-integration`).

Lint: clean on new files (`ruff check` on `test_doc_index_jobs_migration.py` and `models.py` — 0 errors).

Typecheck: **Success: no issues found** (`make typecheck`).

## Observations

- `code_index_jobs` has `updated_at` but `doc_index_jobs` does not — the watermark for re-indexing is tracked at the LanceDB layer (`updated_at` on work items), not in the job table.
- No FTS trigger on `doc_index_jobs` — this table is never searched by content.
- Status is plain TEXT (application-layer validation only), same as `code_index_jobs`.
