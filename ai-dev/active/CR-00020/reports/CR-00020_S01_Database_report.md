# CR-00020 S01 Database Report

## What was done

Implemented S01 (Database) for CR-00020 — Store work item evidences as BLOBs in the database.

### Changes made

1. **Added `EvidencePhase` enum** (`orch/db/models.py`):
   - Python enum with values `pre` and `post`
   - Mirrors the PostgreSQL enum created in the migration

2. **Added `WorkItemEvidence` ORM model** (`orch/db/models.py`):
   - `__tablename__ = "work_item_evidences"`
   - Columns: `id` (UUID, PK), `project_id`, `work_item_id`, `phase` (EvidencePhase), `filename`, `content_type`, `content` (LargeBinary/BYTEA), `size_bytes`, `captured_at`, `step_id` (nullable)
   - Unique constraint: `(project_id, work_item_id, phase, filename)` → `uq_evidence_per_file`
   - FK without cascade: `fk_evidence_work_item` references `work_items(project_id, id)` — **no ON DELETE CASCADE** (evidences survive work_item deletion per AC6)
   - Index: `ix_evidence_project_item_phase (project_id, work_item_id, phase)`

3. **Generated Alembic migration** (`orch/db/migrations/versions/d6b67d4ecb9f_add_work_item_evidences.py`):
   - Creates `evidence_phase` enum via `CREATE TYPE IF NOT EXISTS` (reentrant)
   - Creates `work_item_evidences` table with all columns, FK, unique constraint, index
   - Uses `phase` as TEXT then ALTERs to enum type to avoid conflicts with existing schema
   - `downgrade()` drops table and enum

4. **Updated schema documentation** (`docs/IW_AI_Core_Database_Schema.md`):
   - Added Section 8 documenting `evidence_phase` enum and `work_item_evidences` table
   - Explains FK-without-cascade rationale (evidences survive archival)

## Test results

- **Unit tests**: 1385 passed ✓
- **Integration tests** (excluding pre-existing failures):
  - `test_iw_core_instance_migration.py`: 8 passed ✓
  - `test_pending_migration_log_migration.py`: 11 passed ✓
  - Other integration tests: 918 passed ✓

### Known pre-existing failures (unrelated to CR-00020)
- `test_oss_migration.py`: fails with `UndefinedColumn: column "rationale" of relation "oss_finding" does not exist` — missing migration in test schema
- `test_project_oss_job_migration.py`: fails with `UndefinedColumn: column "base_sha" of relation "project_oss_job" does not exist` — missing migration in test schema

These failures exist in the baseline before CR-00020 changes (the tests don't properly run all migrations before testing).

## Quality checks
- **Lint**: All checks passed on modified files ✓
- **Format**: 3 files formatted (models, migration, previous migration)
- **Typecheck**: No issues found ✓

## Notes
- Migration uses a two-step approach for the enum column: create as TEXT, then ALTER to evidence_phase type. This ensures idempotency when running upgrade multiple times against the same DB.
- The `fk_evidence_work_item` FK has no `ondelete` parameter (defaults to NO ACTION), satisfying AC6 — evidences survive work_item deletion.
- Migration revision hash: `d6b67d4ecb9f`