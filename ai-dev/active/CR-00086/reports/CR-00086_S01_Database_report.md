# CR-00086 S01 Database — Step Report

**Step**: S01 (database-impl)
**Work Item**: CR-00086 — Self-dashboarding of test health
**Date**: 2026-05-28
**Agent**: database-impl

---

## What Was Done

Implemented the Database step of CR-00086: added the `test_health_snapshots` table
and matching SQLAlchemy ORM model, plus a dedicated round-trip test fixture.

## Files Changed

| File | Change |
|------|--------|
| `orch/db/migrations/versions/ea7f8a0d065f_add_test_health_snapshots_table.py` | **New** — Alembic migration: creates table with all 6 columns, composite index, FK, and downgrade |
| `orch/db/models.py` | **Added** — `TestHealthSnapshot` model with `doc=` strings on every column |
| `tests/integration/data_layer/test_test_health_snapshots.py` | **New** — 4 tests covering upgrade, model round-trip, index presence, and downgrade→re-upgrade |

## Migration Details

- **Revision ID**: `ea7f8a0d065f`
- **Parent**: `76250ecb2593` (F-00091 backfill)
- **Columns**: `id BIGSERIAL`, `project_id TEXT NOT NULL`, `ts TIMESTAMPTZ DEFAULT now()`, `metric TEXT NOT NULL`, `value DOUBLE PRECISION NOT NULL`, `meta JSONB NOT NULL DEFAULT '{}'`
- **Index**: `ix_test_health_snapshots_project_metric_ts` on `(project_id, metric, ts DESC)`
- **FK**: `project_id` → `projects.id ON DELETE CASCADE`
- **Migration committed** to git in this step (per CLAUDE.md hard rule)

## TDD Cycle

| Phase | Evidence |
|-------|----------|
| **RED** | All 4 tests failed with `AttributeError: module 'sqlalchemy' has no attribute 'JSONB'` (before importing `JSONB` from `sqlalchemy.dialects.postgresql`) and `NoSuchTableError` (before migration existed) |
| **GREEN** | After adding the migration and model: all 4 tests pass |
| **REFACTOR** | Fixed `_pg_container` fixture convention (`@pytest.mark.usefixtures`), renamed `Session` → `session_maker`, re-formatted long lines |

## Pre-flight Results

| Gate | Result |
|------|--------|
| `make format` | ok (1 file auto-formatted then confirmed clean) |
| `make typecheck` | ok (0 errors in 283 source files) |
| `make lint` | ok (ruff + check_templates.py) |
| `make migration-check` | **PASS** — `test_alembic_upgrade_head_succeeds_from_empty`, `test_alembic_schema_matches_create_all`, `test_alembic_downgrade_base_then_upgrade_head` all green |

## Test Results

```
tests/integration/data_layer/test_test_health_snapshots.py
  test_health_snapshots_table_upgrades_cleanly  PASSED
  test_health_snapshots_model_round_trip        PASSED
  test_health_snapshots_index_exists           PASSED
  test_health_snapshots_downgrade_then_upgrade  PASSED

4 passed in ~8s
```

## Issues / Notes

- **JSONB import**: SQLAlchemy base package doesn't expose `JSONB` directly; must import from `sqlalchemy.dialects.postgresql`. Fixed in migration.
- **Index assertion**: The test now checks for `"project_metric_ts"` substring in the index name rather than `"project_id"` (the PK index `test_health_snapshots_pkey` also contains `project_id` and was the false-positive target).
- **Scalar call pattern**: `conn.execute(text(...)).scalar()` is correct; the test had `text(...).scalar()` (wrong). Fixed.
- **Fixture convention**: `_pg_container` must use `@pytest.mark.usefixtures("pg_container")` not raw parameter injection (ruff PT019).
- The migration file is **committed** in this step per the CLAUDE.md rule (uncommitted revision files cause `alembic upgrade head` to die in worktrees — I-00075/I-00076).

## Next Step

S02 (`qv-gate` migration-check) is the next step in the manifest. It runs the same `make migration-check` command that was just verified in this step — it should be a no-op green from the database-impl perspective, confirming the migration is valid in the QV context.
