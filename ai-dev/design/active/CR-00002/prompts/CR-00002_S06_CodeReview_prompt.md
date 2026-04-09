# CR-00002 S06: Code Review — Test coverage

## Review Scope

Review ALL test files created/modified in S05.

## Review Checklist

1. **Coverage**: Are all 6 sort columns tested? Both directions?
2. **NULL handling**: Is duration sort with NULL `completed_at` tested?
3. **Validation**: Are invalid `sort_by`/`sort_dir` values tested?
4. **Isolation**: Do integration tests use testcontainers (NOT the live DB on port 5433)?
5. **FTS setup**: Do integration tests execute `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `create_all()`?
6. **psycopg driver**: Are testcontainer URLs corrected from `psycopg2` to `psycopg`?
7. **No mocks**: Integration tests use real DB, not mocked sessions.
8. **Assertions**: Are sort order assertions specific (checking adjacent pairs) not just checking first/last?
9. **Test naming**: Follow existing `test_` naming conventions.
