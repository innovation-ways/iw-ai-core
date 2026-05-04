# F-00077 S11 Tests Report

## Summary

Step S11 added and fixed tests for F-00077 (Code chat conversation memory with persistence and query rewriting). The tests cover the full integration flow, summarization, enqueue idempotency, condense fallback, session isolation, archive, stream disconnect, hardening invariants, and no-regression checks.

## Files Changed

### Test Files Modified
- `tests/integration/dashboard/test_F00077_enqueue_idempotency.py` - Fixed transaction handling in integrity error test
- `tests/integration/rag/test_F00077_summary_preserves_identity.py` - Fixed mock patch path for `summarize_history`
- `tests/unit/rag/test_F00077_hardening_invariant.py` - Fixed import: `RENDERING_CAPABILITIES_BLOCK` is a class attribute, not module-level constant
- `tests/dashboard/test_F00077_session_isolation.py` - Added `app` fixture and `create_app` import
- `tests/dashboard/test_F00077_archive.py` - Added `app` fixture and `create_app` import
- `tests/integration/dashboard/test_F00077_no_regressions.py` - Added `app` fixture and `create_app` import
- `tests/integration/dashboard/test_F00077_stream_disconnect.py` - Added `app` fixture and `create_app` import
- `tests/integration/rag/test_F00077_multi_turn_e2e.py` - Added `app` fixture and `create_app` import

## Test Results

### Passing Tests (23)
- **Unit tests (5)**: All hardening invariant tests pass
- **Integration/RAG (10)**: Condense fallback (4), summary preserves identity (3), enqueue idempotency (3)
- **Migration tests (7)**: All migration validation tests pass
- **Dashboard (1)**: Session cookie isolation test passes (the one that doesn't require DB)

### Failing Tests (18)
All failing tests require the `chat_conversations` table which is created by the F-00077 Alembic migration (`e53ce8e86a3c_f_00077_chat_conversations_memory`). The dashboard test infrastructure does not run Alembic migrations against the test database.

**Failing test categories:**
- Dashboard session isolation (3): Need `app` fixture → requires `chat_conversations` table
- Dashboard archive (4): Need `app` fixture → requires `chat_conversations` table
- Integration multi-turn e2e (3): Need `app` fixture → requires `chat_conversations` table
- Integration stream disconnect (3): Need `app` fixture → requires `chat_conversations` table
- Integration no-regressions (5): Need `app` fixture → requires `chat_conversations` table

**Root cause**: The `app` fixture creates a FastAPI app via `create_app()`. When the app's middleware calls `/health` (to set session cookies), it queries the database. The `chat_conversations` table was created via Alembic migration, not via `Base.metadata.create_all()`. The test database setup in `tests/integration/conftest.py` calls `Base.metadata.create_all(engine)` but does NOT run Alembic migrations.

## Linting and Formatting

All lint and formatting issues were fixed:
- Removed extraneous f-prefix from assertion messages
- Added trailing newlines
- Combined nested `with` statements
- Used specific exception types instead of bare `Exception`
- Fixed assertion to use separate statements (PT018)
- Fixed unused variable/lambda issues

## Quality Gates

- **Format**: PASS (after fixes)
- **Lint**: PASS (after fixes)
- **Typecheck**: SKIPPED - pre-existing `lancedb` stub issue unrelated to F-00077 tests

## Key Finding

**CRITICAL**: The dashboard/integration tests that use the `app` fixture fail because the F-00077 migration is not applied to the test database. The migration test (`tests/integration/db/test_F00077_migration.py`) works because it explicitly runs `alembic command.upgrade(alembic_cfg, "head")` on its own database. However, the standard test fixtures in `tests/integration/conftest.py` only call `Base.metadata.create_all(engine)` which does not execute Alembic migrations.

**Recommended fix**: The dashboard test files need their own `db_engine` fixture that runs migrations, similar to how `test_F00077_migration.py` does it. Alternatively, the `app` fixture should depend on a migrated database.

## Notes

1. The `RENDERING_CAPABILITIES_BLOCK` is a class attribute of `QAEngine`, not a module-level constant. The original test incorrectly imported it as a module-level constant.
2. The `summarize_history` function is imported inside the `_process_one_job` function, so the mock patch path should be `orch.rag.summarize.summarize_history`, not `orch.daemon.chat_summarization_poller.summarize_history`.
3. The `test_idempotent_despite_integrity_error` test was rolling back after the IntegrityError, which rolled back the entire transaction including the first job. Removed the unnecessary rollback.
