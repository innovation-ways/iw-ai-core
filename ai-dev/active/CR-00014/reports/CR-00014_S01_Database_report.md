# CR-00014 S01 — Database Implementation Report

## Summary

Step S01 (database-impl) for CR-00014 completed successfully. Implemented the `iw_core_instance` single-row table and its Alembic migration, plus ORM model and integration tests.

## Files Changed

| File | Change |
|------|--------|
| `orch/db/migrations/versions/2bd86f8c105c_add_iw_core_instance.py` | New Alembic migration |
| `orch/db/models.py` | Added `IwCoreInstance` ORM model |
| `tests/integration/test_iw_core_instance_migration.py` | New integration test (3 tests) |

## What Was Done

### 1. Alembic Migration (`2bd86f8c105c_add_iw_core_instance.py`)

- Chained from `824e6e6f34ee` (current head)
- Creates `pgcrypto` extension (idempotent via `IF NOT EXISTS`)
- Creates `iw_core_instance` table with:
  - `id SMALLINT PRIMARY KEY` with `CHECK (id = 1)` constraint
  - `instance_id UUID NOT NULL`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - Table-level comment: "Orchestration DB identity fingerprint — see CR-00014"
- Seeds a row: `INSERT ... SELECT 1, gen_random_uuid() WHERE NOT EXISTS (...)`
- Downgrade: `DROP TABLE iw_core_instance` (pgcrypto is shared — not dropped)

**Note**: Used `WHERE NOT EXISTS` pattern instead of `ON CONFLICT DO NOTHING` because PostgreSQL requires a unique constraint (not just a CHECK constraint) for `ON CONFLICT` target.

### 2. ORM Model (`IwCoreInstance`)

- Placed near `MigrationLock` in `models.py`
- Uses SQLAlchemy 2.0 `Mapped[]` style
- Columns: `id` (SmallInteger PK), `instance_id` (UUID), `created_at` (DateTimeTZ)
- `CheckConstraint("id = 1")` matches the migration
- No relationships or FKs (standalone singleton table)
- Imports added: `uuid`, `SmallInteger`, `CheckConstraint`, `UUID` from dialects

### 3. Integration Tests

Three tests in `tests/integration/test_iw_core_instance_migration.py`:

1. **`test_table_created_and_seeded`**: Verifies table exists with exactly 1 row, `instance_id` is a valid UUID v4, `created_at` is set
2. **`test_check_constraint_prevents_second_row`**: Verifies CHECK constraint raises `IntegrityError` when inserting id=2
3. **`test_downgrade_and_upgrade_round_trip`**: Downgrades (table dropped), then upgrades (table re-created with new UUID)

**Test fixture note**: The `db_engine` fixture sets `IW_CORE_DB_*` env vars from the testcontainer URL before importing `orch.config`, so that `env.py`'s `get_db_url()` call uses the testcontainer URL instead of `.env`.

## Test Results

```
tests/integration/test_iw_core_instance_migration.py: 3 passed
make test-integration: 754 passed, 7 skipped
make lint: 2 pre-existing errors in unrelated files (ARG001 in item_commands.py, W292 in test_item_report_cli.py)
```

## New Alembic Head

Revision hash: `2bd86f8c105c` (previously generated via `alembic revision`)

## Blockers

None.

## Notes

- The migration uses `SELECT ... WHERE NOT EXISTS` for idempotent seeding because PostgreSQL's `ON CONFLICT` requires a unique index, and a CHECK constraint alone does not qualify.
- The migration lock was acquired at step start and released at step end.
- UUIDs are intentionally different per deployment (via `gen_random_uuid()`). This is the design intent per CR-00014 AC5.
