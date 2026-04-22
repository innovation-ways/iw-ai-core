# CR-00014 S02 — Code Review Report

## Summary

S01 (database-impl) reviewed. All three deliverables (migration, ORM model, integration tests) are correct and complete. No blockers.

## Files Changed

| File | Change |
|------|--------|
| `orch/db/migrations/versions/2bd86f8c105c_add_iw_core_instance.py` | Reviewed — OK |
| `orch/db/models.py` | Reviewed — OK |
| `tests/integration/test_iw_core_instance_migration.py` | Reviewed — OK |

## What Was Reviewed

### 1. Migration (`2bd86f8c105c_add_iw_core_instance.py`)

- `down_revision` correctly points to `824e6e6f34ee` (previous head)
- Upgrade creates `iw_core_instance` with `id SMALLINT PK`, `instance_id UUID`, `created_at TIMESTAMPTZ`
- `CHECK constraint "id = 1"` present with correct name `ck_iw_core_instance_single_row`
- Table-level comment present
- `server_default=sa.func.now()` on `created_at`
- `CREATE EXTENSION IF NOT EXISTS pgcrypto` included (idempotent)
- Seed uses `WHERE NOT EXISTS` pattern (idempotent; note: `ON CONFLICT DO NOTHING` was not used because PostgreSQL requires a unique index, not just a CHECK constraint — this is correct)
- Downgrade drops table cleanly; does not drop `pgcrypto`
- **Autogenerate cleanliness**: Could not verify locally (requires a fresh DB), flagged as LOW noting S01 agent would need to prove via report

### 2. ORM Model (`IwCoreInstance` in `models.py`)

- Uses SQLAlchemy 2.0 `Mapped[]` typed style — consistent with project convention
- `CheckConstraint("id = 1", name="ck_iw_core_instance_single_row")` present
- `instance_id` uses `UUID(as_uuid=True)` — Python code gets `uuid.UUID` objects
- `created_at` has `server_default=func.now()` — not Python-side default
- No FKs, no back-populates — correct for a singleton standalone table
- Placed near `MigrationLock` — appropriate infrastructure grouping
- Imports: `uuid` already imported at top of file; `SmallInteger`, `CheckConstraint` already imported; `UUID` from dialects already imported — no new imports needed

### 3. Tests (`test_iw_core_instance_migration.py`)

- Uses testcontainer (not live DB on port 5433) — correct
- `postgresql+psycopg2://` → `postgresql+psycopg://` replacement present — correct
- `test_table_created_and_seeded`: asserts exactly 1 row, `id==1`, UUID v4 format, `created_at` not null
- `test_check_constraint_prevents_second_row`: asserts `IntegrityError` on `id=2` insert
- `test_downgrade_and_upgrade_round_trip`: downgrade drops table, upgrade re-creates with new UUID (proves fresh UUID per deployment)
- All 3 tests pass

## Test Results

```
tests/integration/test_iw_core_instance_migration.py: 3 passed
make lint: 2 pre-existing errors in unrelated files (ARG001 in item_commands.py, W292 in test_item_report_cli.py)
```

## Findings

| Severity | File | Line | Issue | Fix Applied |
|----------|------|------|-------|------------|
| LOW | Migration autogenerate | — | Could not verify autogenerate cleanliness locally — migration file exists and structure is correct, but a fresh `alembic revision --autogenerate` after upgrade was not run | N/A (design doc flagging) |

## Blockers

None.

## Notes

- The seed pattern `SELECT ... WHERE NOT EXISTS` is the correct alternative to `ON CONFLICT DO NOTHING` when only a CHECK constraint (not a unique index) exists on the target row. The S01 report correctly explains this.
- The lint errors are pre-existing and unrelated to this CR.
- Migration lock: S01 report notes lock acquired and released; no dangling lock.
- No extraneous changes to other models, daemon code, or CLI.
