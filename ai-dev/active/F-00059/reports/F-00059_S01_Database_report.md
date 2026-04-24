# F-00059_S01_Database_report

## What was done

Implemented the database layer for F-00059 (functional design documents):

1. **ORM model changes** (`orch/db/models.py`):
   - Added three new columns to `WorkItem`: `functional_doc_path`, `functional_doc_content`, `functional_doc_search` (TSVECTOR)
   - Added `FUNCTIONAL_DOC_FTS_FUNCTION_SQL` and `FUNCTIONAL_DOC_FTS_TRIGGER_SQL` constants
   - Added `idx_work_items_functional_doc_search` GIN index to `__table_args__`

2. **Alembic migration** (`orch/db/migrations/versions/1fb2eb17b580_add_functional_doc_columns_to_work_items.py`):
   - Adds three columns, creates trigger function + trigger, creates GIN index
   - Downgrade drops index → trigger → function → columns (order verified)

3. **Testcontainer FTS install** (`tests/integration/conftest.py`):
   - Installs `FUNCTIONAL_DOC_FTS_FUNCTION_SQL` + `FUNCTIONAL_DOC_FTS_TRIGGER_SQL` after `Base.metadata.create_all()`

4. **Integration tests** (`tests/integration/test_work_items_functional_doc_fts.py`):
   - FTS trigger tests: insert populates search, update regenerates, GIN index query returns row, independence from design_doc_search
   - Migration round-trip test: upgrade → downgrade → verify clean state → re-upgrade succeeds

## Files changed

| File | Change |
|------|--------|
| `orch/db/models.py` | +3 columns, +FTS constants, +GIN index |
| `orch/db/migrations/versions/1fb2eb17b580_add_functional_doc_columns_to_work_items.py` | New migration |
| `tests/integration/conftest.py` | +FTS trigger install |
| `tests/integration/test_work_items_functional_doc_fts.py` | New test file |

## Test results

- `make test-integration`: **6 passed** (5 FTS trigger tests + migration round-trip)
- `make lint`: **pass** (all modified files pass ruff)
- `make typecheck`: **pass** (148 source files, no issues)

## Notes

- Migration uses raw SQL `op.execute(text(...))` for trigger/function creation since autogenerate doesn't capture PL/pgSQL
- The migration round-trip test uses direct SQL (not Alembic CLI) to avoid env.py loading .env
- Existing `FTS_FUNCTION_SQL`/`FTS_TRIGGER_SQL` unchanged (Invariant 7)
