# F-00090 S01 — Database Report

**Work Item**: F-00090 — Regression-rate tracking
**Step**: S01 (database-impl)
**Agent**: database-impl
**Date**: 2026-05-27

## What was done

Implemented the database layer for F-00090 — added five nullable columns to `WorkItem`, a PostgreSQL ENUM type `regression_classification_enum`, and an index, following the exact conventions used by the existing models.

### Changes

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `RegressionClassification` enum, `_regression_classification_col` helper, five new fields on `WorkItem`, and one new `Index` in `__table_args__` |
| `orch/db/migrations/versions/d43ea9e75e8f_f_00090_regression_link_fields.py` | Alembic revision: creates ENUM, adds 5 columns with `comment=` strings, creates index; complete `downgrade()` drops index, columns, ENUM |
| `docs/IW_AI_Core_Database_Schema.md` | Documented the new ENUM type and the five new columns under `work_items`; added the new index |

### New columns on `work_items`

| Column | Type | Null? | Comment |
|--------|------|-------|---------|
| `introduced_by_work_item_id` | TEXT | NULL | ID of the work item whose merge introduced the regression |
| `introduced_by_commit_sha` | TEXT | NULL | Optional operator-supplied commit SHA |
| `regression_classification` | `regression_classification_enum` | NULL | `regression`, `pre_existing`, or `unknown` — NULL means not yet classified |
| `classified_at` | TIMESTAMPTZ | NULL | UTC timestamp of last classification |
| `classified_by` | TEXT | NULL | `'operator:<user>'` or `'heuristic:auto'` |

### New index

- `ix_work_items_introduced_by_work_item_id` on `introduced_by_work_item_id` — used for badge-count rollups on Batches/History views (Invariant 7 / AC1)

### New PostgreSQL type

- `regression_classification_enum` with values `'regression'`, `'pre_existing'`, `'unknown'` — created in `upgrade()`, dropped in `downgrade()`

## Test results

| Gate | Result |
|------|--------|
| `make format` | ok (ruff auto-fixed 1 file) |
| `make typecheck` | ok (0 errors on 279 source files) |
| `make lint` | ok (ruff + Jinja2 template check) |
| `make migration-check` | **PASS** — 3/3 round-trip tests passed |

`make migration-check` verified:
- `upgrade head` → `downgrade base` → `upgrade head` round-trips cleanly
- `upgrade head` succeeds from empty
- Schema after `upgrade head` matches `Base.metadata.create_all()`

No orphaned ENUM types, no leftover indexes (Invariant 7 verified).

## TDD evidence

`tdd_red_evidence: "n/a — schema/migration only; verified by make migration-check round-trip"`

## Notes

- `RegressionClassification` Python enum lives alongside the other `WorkItem`-adjacent enums (e.g. `WorkItemPhase`, `WorkItemStatus`). The ENUM type name is `regression_classification_enum` (matching the pattern of `work_item_status` / `work_item_phase` etc. in the file).
- `_regression_classification_col` uses `create_type=False` (matching `_doc_type_col`, `_doc_status_col`, `_job_status_col`, `_editorial_category_col`) because the PG type is created explicitly in the migration rather than by SQLAlchemy at table-creation time.
- All five columns are nullable — no backfill step needed at migration time (operator runs `scripts/backfill_regression_classification.py` manually, per S05).
- No FK constraint was added on `introduced_by_work_item_id` because the design doc specifies validation at the service/CLI layer, not DB level (Invariant 4 cross-references are enforced in `orch/regression_link_service.py`).
- The `chat_tabs` comment-alter operations that appeared in the autogenerate output were unrelated (a comment-only change from a prior in-flight migration); the final revision file contains only F-00090 operations.