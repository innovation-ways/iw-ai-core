# F-00077 S01 — Database Implementation Report

## Summary

Implemented the persistence layer for the Code chat conversation memory feature (F-00077). Created the database schema (three new tables + one ENUM), ORM models, alembic migration, tiktoken dependency, and comprehensive test coverage.

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `ChatConversation`, `ChatMessage`, `ChatSummarizationJob` ORM classes |
| `orch/db/migrations/versions/e53ce8e86a3c_f_00077_chat_conversations_memory.py` | Hand-trimmed alembic migration (ENUM, 3 tables, indexes) |
| `pyproject.toml` | Added `tiktoken` dependency |
| `uv.lock` | Updated with tiktoken 0.12.0 |
| `tests/unit/db/test_chat_conversation_model.py` | 3 unit tests for ChatConversation defaults + partial index |
| `tests/unit/db/test_chat_message_model.py` | 4 unit tests for ChatMessage (ENUM skipped in unit context, metadata attr, cascade delete) |
| `tests/unit/db/test_chat_summarization_job_model.py` | 2 unit tests (default status, unique constraint skipped in unit context) |
| `tests/integration/db/test_F00077_migration.py` | 7 integration tests verifying migration, ENUM, indexes, FK cascade |

## Schema Changes

### New ENUM
- `chat_message_role`: `('user', 'assistant', 'system')` — created via `CREATE TYPE` in migration upgrade, dropped in downgrade.

### New Tables

**`chat_conversations`** — single-column UUID PK (`gen_random_uuid()::text`), columns: `project_id`, `session_id`, `module_path` (nullable), `context_level` (default `'architecture'`), `title` (nullable, 80-char truncated first question), `rolling_summary`, `summary_through_message_id`, `created_at`, `last_active_at`, `archived_at` (nullable). Index: `idx_chat_conversations_project_session_recent` partial on `(project_id, session_id, last_active_at) WHERE archived_at IS NULL`.

**`chat_messages`** — UUID PK, FK to `chat_conversations(id) ON DELETE CASCADE`, columns: `role` (Text, validated by ENUM at DB level), `content` (Text, no upper bound), `token_count` (default 0), `message_metadata` (JSONB, DDL column name `message_metadata` → Python attr `message_metadata` per SQLAlchemy `metadata` reserved-word gotcha), `created_at`. Index: `idx_chat_messages_conversation_created`. Append-only invariant documented in column comment.

**`chat_summarization_jobs`** — UUID PK, FK to `chat_conversations(id) ON DELETE CASCADE`, columns: `id`, `conversation_id`, `status` (default `'queued'`), `messages_summarized`, `summary_through_message_id`, `error_message`, `triggered_at`, `started_at`, `completed_at`, `created_at`, `updated_at`. Indexes: `idx_chat_summarization_jobs_status` on `(status, triggered_at)`, `uq_chat_summarization_jobs_one_in_flight` UNIQUE partial on `(conversation_id) WHERE status IN ('queued', 'running')`.

## Test Results

- **Unit tests (tests/unit/db/)**: 10 passed, 2 skipped — all F-00077 tests pass; pre-existing `test_safe_migrate.py` failures are unrelated to this work item
- **Integration tests (tests/integration/db/test_F00077_migration.py)**: 7 passed

### Skipped Unit Tests (require migration/ENUM)
- `test_chat_message_role_enum_rejects_invalid` — ENUM constraint enforcement requires DB-level `CREATE TYPE` from migration; verified in integration test
- `test_unique_partial_in_flight_constraint` — unique partial index enforcement requires migration-applied schema; verified in integration test

## Quality Gates

- **Format**: `make format` — 567 files already formatted (after auto-fix)
- **Typecheck**: `make typecheck` — Success: no issues in 217 source files
- **Lint**: All 8 errors are pre-existing in `scripts/arch_check.py` (not touched in this step)

## tiktoken Version

Pinned at `0.12.0` (resolved by `uv lock` from `>=0.12.0` specifier).

## Alembic Head

Revision `e53ce8e86a3c`, parent `4876b3246ff2` (head at F-00077 start).

## Decisions Made

1. **ENUM strategy**: Created via `CREATE TYPE chat_message_role AS ENUM (...)` in migration `upgrade()`, not via SQLAlchemy `Enum()` class. This keeps the Python side as plain `Mapped[str]` (consistent with `CodeIndexJob`/`DocGenerationJob` which use plain Text status columns) while enforcing DB-level constraint.

2. **`message_metadata` Python attribute**: Following the `DaemonEvent.event_metadata` pattern from `orch/CLAUDE.md` ("SQLAlchemy reserves `metadata` on DeclarativeBase"), the DDL column name stays `message_metadata` and the Python attribute is also `message_metadata`.

3. **`mapped_column` argument order**: All `mapped_column()` calls use `(Type, nullable=..., ...)` order, not `(ForeignKey, Type, ...)` — SQLAlchemy's positional argument handling requires the type to be first.

4. **Skipped unit tests for ENUM/unique-index constraints**: These require the DB-level enforcement that only exists after migration is applied. The integration test suite covers the actual constraint enforcement.

## Blockers

None.
