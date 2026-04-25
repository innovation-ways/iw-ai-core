# F-00062 S01 Database Report

## What was done

Implemented the schema changes for per-worktree container isolation (F-00062):

1. **Added `setup_failed` to `BatchItemStatus` enum** (`orch/db/models.py:155`):
   - `setup_failed = "setup_failed"` was added to the Python enum

2. **Added three nullable columns to `BatchItem` model** (`orch/db/models.py:939-955`):
   - `worktree_db_port: Mapped[int | None]` — discovered Postgres host port; NULL for legacy worktrees
   - `worktree_app_port: Mapped[int | None]` — discovered app server host port; NULL when no app service or legacy
   - `worktree_compose_path: Mapped[str | None]` — absolute path to rendered docker-compose file; NULL for legacy

3. **Generated Alembic migration** (`orch/db/migrations/versions/550aecbbd42b_f_00062_add_worktree_compose_stack_.py`):
   - Contains `ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'setup_failed'` inside `op.get_context().autocommit_block()` (PostgreSQL requires this outside transaction)
   - Adds three `op.add_column` for the new batch_items columns
   - Downgrade drops the three columns; leaves enum label as orphan (PostgreSQL cannot drop enum values — same trade-off as CR-00019/CR-00021)

4. **Updated schema docs** (`docs/IW_AI_Core_Database_Schema.md`):
   - Added `setup_failed` to the `batch_item_status` enum listing
   - Added column table documenting all three new columns with descriptions
   - Added Invariant #6 note (all three columns are NULL together or all non-NULL)
   - Added `setup_failed` to the status meanings table

5. **Wrote unit test** (`tests/unit/test_batch_item_columns.py`):
   - 9 tests covering column presence, types, nullability, and default values
   - Tests for `setup_failed` enum existence

## Files changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `setup_failed` enum value + three new columns on `BatchItem` |
| `orch/db/migrations/versions/550aecbbd42b_f_00062_add_worktree_compose_stack_.py` | New migration file |
| `docs/IW_AI_Core_Database_Schema.md` | Updated enum + added column docs + Invariant #6 |
| `tests/unit/test_batch_item_columns.py` | New unit test file |

## Test results

- **Unit tests**: `make test-unit` — **1472 passed** (including 9 new tests)
- **Ruff lint on changed files**: All passed (pre-existing errors in `test_qa_engine_classifier.py` unrelated to this change)
- **mypy on changed files**: Success — no issues found

## Notes

- `setup_failed` enum value was **added** (did not pre-exist in the codebase)
- The migration uses the CR-00019/CR-00021 pattern for enum addition (autocommit block)
- On downgrade, the `setup_failed` enum label remains as a dormant orphan — PostgreSQL limitation
- The `make lint` failure is due to pre-existing E501 line-length errors in `tests/unit/test_qa_engine_classifier.py` (not introduced by this change)
