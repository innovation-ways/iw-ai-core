# CR-00017 S01 Database Report

## Summary

Created the `pending_migration_log` table and `PendingMigrationLog` ORM model for the daemon-driven 3-phase migration pipeline audit log (AC9 from CR-00017).

## Files Changed

1. **`orch/db/migrations/versions/637c16395a0b_add_pending_migration_log.py`** — New alembic migration
   - Creates `pending_migration_log` table with BIGSERIAL id (via sequence), CHECK constraints for `direction` and `phase` enums, indexes on `(batch_id, started_at DESC)` and `(revision, phase)`.
   - Downgrade drops indexes, sequence (CASCADE), and table.

2. **`orch/db/models.py`** — Added `PendingMigrationLog` ORM model
   - Located near `MigrationLock` and `DaemonEvent` (audit/infrastructure tables)
   - Uses `CheckConstraint` with explicit `name=` for alembic autogenerate compatibility
   - Optional `batch` relationship (ORM-only; DB-level FK not enforced due to batches.id being TEXT vs batch_id being BIGINT — type mismatch documented in test)

3. **`tests/integration/test_pending_migration_log_migration.py`** — New RED test (8 tests)
   - `test_table_exists_with_columns`: verifies all 12 columns with correct types
   - `test_direction_check_constraint` / `test_phase_check_constraint`: verify CHECK constraints reject invalid values
   - `test_valid_enum_values_accepted`: verify valid enum combos are accepted
   - `test_indexes_exist`: verify both indexes with correct column ordering
   - `test_batch_id_accepts_values`: verify batch_id stores values (DB FK not enforceable due to type mismatch)
   - `test_downgrade_drops_table` / `test_upgrade_recreates_table_empty`: round-trip via alembic

## Test Results

- **Integration tests**: 8 passed, 0 failed
- **Lint**: mypy/ruff clean on all 3 changed files (pre-existing `ARG001` in `orch/cli/item_commands.py` unrelated to this step)

## Notes

- `batch_id` is BIGINT in `pending_migration_log` but `batches.id` is TEXT (composite PK). DB-level FK constraint cannot be enforced. The FK is modeled in the ORM only. The design doc's schema is followed — column type is BIGINT as specified.
- Sequence is explicitly created and dropped (CASCADE in downgrade) because SQLAlchemy's `BigInteger` type with `autoincrement=True` does not produce a PostgreSQL identity column in SQLAlchemy 2.0.50 with PostgreSQL 15.
- Autogenerate is clean — no diff produced when running `alembic revision --autogenerate` at current head.

## Migration Lock

Released (status was free at step start).