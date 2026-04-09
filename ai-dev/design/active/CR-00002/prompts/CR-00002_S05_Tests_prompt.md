# CR-00002 S05: Tests — Sort functionality coverage

## Context

Read `CLAUDE.md` for testing rules (NON-NEGOTIABLE). All DB tests use testcontainers. Never connect to the live database on port 5433.

## Tests to Write

### Unit Tests (in `tests/unit/`)

Create `tests/unit/test_history_sort.py`:

1. **test_sort_by_whitelist_rejects_invalid** — verify that invalid `sort_by` values (e.g., `"nonexistent"`, `"; DROP TABLE"`, `""`) are normalized to `"created_at"`
2. **test_sort_dir_rejects_invalid** — verify that invalid `sort_dir` values (e.g., `"sideways"`, `""`) are normalized to `"desc"`
3. **test_default_sort_params** — verify that omitting params gives `created_at` + `desc`

These can test the validation logic directly if extracted to a helper, or test the route handler with a mock DB session.

### Integration Tests (in `tests/integration/`)

Create or extend tests in `tests/integration/` to cover:

1. **test_history_sort_by_id_asc** — insert multiple work items with different IDs, query with `sort_by=id&sort_dir=asc`, verify ascending order
2. **test_history_sort_by_title_desc** — insert items with known titles, query with `sort_by=title&sort_dir=desc`, verify descending alphabetical order
3. **test_history_sort_by_created_at_default** — query with no sort params, verify default `created_at` desc ordering
4. **test_history_sort_by_duration_with_nulls** — insert items with and without `completed_at`, sort by duration asc, verify NULL durations appear last
5. **test_history_sort_preserved_with_filters** — apply a type filter AND sort_by=title, verify both are respected
6. **test_history_sort_preserved_across_pages** — create >20 items, sort by title, verify page 2 continues the sort order

### Testing Setup

For integration tests, follow the existing patterns in `tests/integration/`:
- Use testcontainers for PostgreSQL
- After `Base.metadata.create_all()`, execute `FTS_FUNCTION_SQL` and `FTS_TRIGGER_SQL`
- Replace `psycopg2` URLs with `psycopg` in connection strings
- Create a test project and work items with `completed`/`failed` status for history queries

## Files to Create/Modify

- `tests/unit/test_history_sort.py` (new)
- `tests/integration/test_history_sort.py` (new) or extend `tests/integration/test_dashboard_remaining.py`

## Acceptance Criteria

- All tests pass with `make test-unit` and `make test-integration`
- Sort whitelist validation is tested
- All 6 sortable columns are covered in at least one direction
- NULL duration handling is tested
- Sort + filter combination is tested
- Sort + pagination combination is tested
