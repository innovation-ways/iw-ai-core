# CR-00078 S01 — Database report

**Step**: S01 (database-impl)
**Work Item**: CR-00078 — Per-batch ignore overlap & force-start
**Date**: 2026-05-23

---

## What was done

### 1. `BatchOverlapIgnore` ORM model added to `orch/db/models.py`

Placed immediately before `IwCoreInstance` (near related batch models). Uses SQLAlchemy 2.0 `Mapped[]` declarative style matching all existing models.

Columns:
- `project_id`, `batch_id`, `held_item_id`, `blocking_item_id`, `file_pattern` — all `Mapped[str]` and all part of the composite PK
- `ignored_by: Mapped[str]` — operator placeholder (`"operator"` literal until auth lands)
- `ignored_at: Mapped[datetime]` — `DateTime(timezone=True)` with `server_default=func.now()` (matches every other timestamptz column in the repo)
- `reason: Mapped[str | None]` — nullable `Text`, forward-compat for future CR

`__table_args__`:
- FK to `batches(project_id, id)` with `ondelete="CASCADE"`
- FK to `batch_items(project_id, batch_id, work_item_id)` with `ondelete="CASCADE"`
- Table-level comment documenting the composite-PK per-batch isolation property and exact-string-match note

### 2. Alembic migration: `3a3dfec7bfbd_cr_00078_add_batch_overlap_ignore.py`

Revision: `3a3dfec7bfbd`
Parent: `aeb0e4106b55`

`upgrade()` creates the table with:
- Five `sa.Text()` PK columns
- `ignored_by` NOT NULL `Text`
- `ignored_at` with `server_default=sa.text("now()")` and `DateTime(timezone=True)`
- Nullable `reason` `Text`
- Both composite `ForeignKeyConstraint`s with `ondelete="CASCADE"` (autogenerate caught both correctly)
- `sa.PrimaryKeyConstraint` over all five PK columns
- Table comment

`downgrade()`: `op.drop_table("batch_overlap_ignore")` — clean and reversible

**Verification**: Both FKs confirmed present in the generated migration:
```
sa.ForeignKeyConstraint(['project_id', 'batch_id'], ['batches.project_id', 'batches.id'], ondelete='CASCADE')
sa.ForeignKeyConstraint(['project_id', 'batch_id', 'held_item_id'], ['batch_items.project_id', 'batch_items.batch_id', 'batch_items.work_item_id'], ondelete='CASCADE')
```

No incidental `alter_column` changes to unrelated tables (the autogenerate wanted to add comment re-applies to `chat_tabs` columns — these were stripped from the final file).

---

## Files changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `BatchOverlapIgnore` class (before `IwCoreInstance`) |
| `orch/db/migrations/versions/3a3dfec7bfbd_cr_00078_add_batch_overlap_ignore.py` | New migration file |

---

## Test results

### `make migration-check`
```
tests/integration/test_migrations_round_trip.py::test_alembic_upgrade_head_succeeds_from_empty PASSED
tests/integration/test_migrations_round_trip.py::test_alembic_downgrade_base_then_upgrade_head PASSED
tests/integration/test_migrations_round_trip.py::test_alembic_schema_matches_create_all PASSED
3 passed in 8.78s
```
**Status**: PASSED — schema parity vs `Base.metadata.create_all()`, upgrade + downgrade round-trip all clean.

### `make format` / `make typecheck` / `make lint`
All pre-flight gates passed (format, typecheck, lint all clean).

---

## TDD RED Evidence

`n/a — schema-only step; behavioural tests for the model live in S10 (test_batch_overlap_ignore.py). The migration round-trip itself is exercised by `make migration-check` (S03) and `make test-integration` (S17).`

---

## Notes / Observations

1. **Both FKs verified present**: autogenerate correctly detected both the `(project_id, batch_id)` FK to `batches` and the three-column `(project_id, batch_id, held_item_id)` FK to `batch_items`. No hand-edits were needed for the FKs themselves.
2. **No incidental drift**: autogenerate also wanted to re-apply comment-only `alter_column` statements to `chat_tabs` columns from the parent revision — these were removed from the final migration; they would cause noise in future diffs without adding any functionality.
3. **No `relationship()` back-ref added**: consistent with existing models that use composite PKs (e.g. `MigrationLock`); the ORM mapper-level join behaviour is driven by the table-level `ForeignKeyConstraint` entries.
4. **`ignored_at` uses `_TIMESTAMPTZ`** (`DateTime(timezone=True)`) — exact same type as every other timestamp column in the repo (e.g. `Batch.created_at`, `DaemonEvent.created_at`).