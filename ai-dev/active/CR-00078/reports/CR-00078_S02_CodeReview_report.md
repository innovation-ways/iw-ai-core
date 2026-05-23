# CR-00078 S02 — Code Review report

**Step**: S02 (code-review-impl)
**Work Item**: CR-00078 — Per-batch ignore overlap & force-start
**Date**: 2026-05-23

---

## What was done

Review of S01's model + migration implementation for `BatchOverlapIgnore`. Verification included:
1. Full model reading (`orch/db/models.py`)
2. Full migration reading (`3a3dfec7bfbd_cr_00078_add_batch_overlap_ignore.py`)
3. S01 report reading (`ai-dev/active/CR-00078/reports/CR-00078_S01_Database_report.md`)
4. Re-ran `make migration-check` to verify schema parity independently

---

## Model review — `BatchOverlapIgnore`

| Aspect | Assessment |
|--------|------------|
| Composite PK (5 cols) | ✅ `project_id`, `batch_id`, `held_item_id`, `blocking_item_id`, `file_pattern` — all `Mapped[str]` with `primary_key=True` inline |
| `ignored_by` | ✅ `Mapped[str]`, `nullable=False` — no server_default (operator must supply it) |
| `ignored_at` | ✅ `DateTime(timezone=True)` via `_TIMESTAMPTZ`, `nullable=False`, `server_default=func.now()` — matches every other timestamptz col in the repo |
| `reason` | ✅ `Mapped[str \| None]`, `Text`, `nullable=True` |
| FK to batches | ✅ Composite `(project_id, batch_id)` → `(batches.project_id, batches.id)`, `ondelete="CASCADE"` |
| FK to batch_items | ✅ Composite `(project_id, batch_id, held_item_id)` → `(batch_items.project_id, batch_items.batch_id, batch_items.work_item_id)`, `ondelete="CASCADE"` |
| Imports | ✅ All required symbols already imported (`ForeignKeyConstraint` present) — no new imports needed |
| Placement | ✅ Placed between `BatchItem` and `MigrationLock` — near related batch models |
| Table comment | ✅ Documents composite-PK per-batch isolation and exact-string-match semantics |

**CRITICAL/HIGH findings: 0**

---

## Migration review — `3a3dfec7bfbd_cr_00078_add_batch_overlap_ignore.py`

| Aspect | Assessment |
|--------|------------|
| Revision/revises | ✅ `3a3dfec7bfbd` / `aeb0e4106b55` — sane parent |
| `upgrade()` creates table | ✅ All 5 PK cols + `ignored_by` + `ignored_at` (with `server_default=sa.text("now()")`) + `reason` (nullable) |
| Both FKs | ✅ Present with `ondelete="CASCADE"` on each |
| `downgrade()` | ✅ Exactly `op.drop_table("batch_overlap_ignore")` — no extra operations |
| No drift | ✅ No `alter_column` statements touching other tables |
| CR reference in comment | ✅ Top-of-file comment names CR-00078 and explains design |

**CRITICAL/HIGH findings: 0**

---

## Round-trip verification

```bash
$ make migration-check
tests/integration/test_migrations_round_trip.py::test_alembic_upgrade_head_succeeds_from_empty PASSED
tests/integration/test_migrations_round_trip.py::test_alembic_downgrade_base_then_upgrade_head PASSED
tests/integration/test_migrations_round_trip.py::test_alembic_schema_matches_create_all PASSED
3 passed in 11.36s
```

- `make migration-check` exit 0 ✅
- Schema parity confirmed ✅
- Upgrade + downgrade round-trip clean ✅

---

## Files changed

| File | Change |
|------|--------|
| None (review step) | — |

---

## Test results

| Suite | Result |
|-------|--------|
| `make migration-check` | ✅ 3/3 passed (11.36s) |

---

## TDD RED Evidence

`n/a — review-only step; model exercised via migration round-trip and schema-parity tests already run by S01.`

---

## Notes

1. **`ignored_at` type**: Uses `_TIMESTAMPTZ` (`DateTime(timezone=True)`) — identical to `Batch.created_at`, `DaemonEvent.created_at`, etc. No inconsistency with the rest of the codebase.
2. **No `relationship()` back-ref added**: Consistent with other composite-PK models (e.g., `MigrationLock`). The table-level `ForeignKeyConstraint` entries drive ORM join behaviour without a back-populates pair.
3. **No import additions required**: All symbols (`ForeignKeyConstraint`, `func`, `Text`, `DateTime`) were already present in the import block.

---

## Findings summary

| Severity | Count | Details |
|----------|-------|---------|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM | 0 | — |
| LOW | 0 | — |

**Status**: ✅ All clear — no blockers. Model and migration are correct and consistent with the existing codebase.