# F-00077 S02 — Code Review Report (Database Implementation)

## Summary

Reviewed the S01 (database-impl) output for F-00077. All checklist items pass.
The implementation is correct, follows project conventions, and introduces no
new violations in the files it changed.

---

## Files Changed by S01

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `ChatConversation`, `ChatMessage`, `ChatSummarizationJob` ORM classes |
| `orch/db/migrations/versions/e53ce8e86a3c_f_00077_chat_conversations_memory.py` | Hand-trimmed alembic migration (ENUM, 3 tables, indexes) |
| `pyproject.toml` | Added `tiktoken>=0.12.0` to `dependencies` |
| `uv.lock` | Updated with tiktoken 0.12.0 |
| `tests/unit/db/test_chat_conversation_model.py` | 3 unit tests |
| `tests/unit/db/test_chat_message_model.py` | 4 unit tests (1 skipped, ENUM requires DB-level constraint) |
| `tests/unit/db/test_chat_summarization_job_model.py` | 2 unit tests (1 skipped, index requires migration) |
| `tests/integration/db/test_F00077_migration.py` | 7 integration tests |

---

## Review Checklist

### 1. Architecture Compliance ✅

- **ORM style**: All three classes use SQLAlchemy 2.0 `Mapped[]` style, consistent with `CodeIndexJob` and all other models in `models.py`.
- **Single-column PK**: `ChatConversation`, `ChatMessage`, `ChatSummarizationJob` each use `id TEXT` as primary key — matching `CodeIndexJob` pattern, NOT composite PK.
- **`message_metadata` attribute**: `ChatMessage` column is named `message_metadata` in DDL; Python attribute is `message_metadata`. The `DeclarativeBase.metadata` collision is avoided exactly as `DaemonEvent.event_metadata` is handled. ✅
- **ENUM strategy**: Created via raw SQL `CREATE TYPE chat_message_role AS ENUM (...)` in migration `upgrade()`. Python side uses `Mapped[str]` (plain Text). No auto-management by SQLAlchemy on `create_all()` — testcontainers cannot raise duplicate-type errors. ✅

### 2. Migration Correctness ✅

- **`down_revision`**: Set to `"4876b3246ff2"` — confirmed correct head before this migration (via `alembic history`). ✅
- **`upgrade()` order**: ENUM → `chat_conversations` → `chat_messages` → `chat_summarization_jobs` → indexes. ✅
- **`downgrade()` order**: `drop_index(uq_...)` → `drop_index(idx_...)` → `drop_table(chat_summarization_jobs)` → `drop_table(chat_messages)` → `drop_table(chat_conversations)` → `DROP TYPE`. Reverse order confirmed. ✅
- **No FTS triggers**: This migration does not touch FTS triggers or unrelated tables. ✅
- **Partial unique index**: `uq_chat_summarization_jobs_one_in_flight` uses `unique=True, postgresql_where=sa.text("status IN ('queued', 'running')")`. ✅
- **Partial index on conversations**: `idx_chat_conversations_project_session_recent` filters `WHERE archived_at IS NULL` with sort by `last_active_at DESC`. ✅

### 3. Code Quality ✅

- **Comments**: All `mapped_column` declarations include a `comment=` string — matches convention in adjacent classes. ✅
- **JSONB default**: Uses `server_default=sa.text("'{}'::jsonb")` — not a lambda. ✅
- **Timestamps**: All `server_default=sa.text("now()")` — consistent with project patterns. ✅
- **`message_metadata` comment**: Documents the append-only exception (same-transaction `metadata.error=true` write). ✅
- **`token_count` comment**: States "set at insert, never updated" semantics. ✅
- **Cascade deletes**: Both `ChatMessage.conversation_id` and `ChatSummarizationJob.conversation_id` declare `ForeignKey("chat_conversations.id", ondelete="CASCADE")`. ✅

### 4. Project Conventions ✅

- **File ordering**: New classes appended after `CodeIndexJob` at line 2061 — existing order preserved. ✅
- **Index naming**: `idx_<table>_<column(s)>` for non-unique, `uq_<table>_<column(s)>` for unique. ✅
- **tiktoken**: Added to `dependencies` (not `dev-dependencies`) in `pyproject.toml`. ✅
- **No psycopg2 references**: No `psycopg2` introduced in any S01 file. ✅

### 5. Testing ✅

- **testcontainers**: All tests use the `pg_engine` testcontainer fixture. ✅
- **psycopg2 replacement**: Applied in all test files (`url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`). ✅
- **FTS SQL run after `create_all()`**: `FTS_FUNCTION_SQL` and `FTS_TRIGGER_SQL` executed after `Base.metadata.create_all(engine)` in all unit test files. ✅
- **Cascade-delete test**: `test_cascade_delete_on_conversation` exists and passes. ✅
- **Unique-partial-index test**: `test_unique_in_flight_constraint_blocks_concurrent_jobs` in integration tests properly verifies both directions. ✅
- **`message_metadata` guard test**: `test_chat_message_python_attribute_is_message_metadata` exists and verifies the Python attribute is NOT the SQLAlchemy-inherited `metadata`. ✅

### 6. Security ✅

- No hardcoded secrets or connection strings in any S01 file. ✅
- No SQL string concatenation in data manipulation — migration is schema-only. ✅

---

## Pre-Review Gate

- **`make lint`** (full project): 8 errors — all pre-existing in `scripts/arch_check.py` (not touched by S01).
- **`make format`**: 567 files already formatted.
- **S01-specific lint/format**: `ruff check` and `ruff format --check` on all S01-changed files pass cleanly. No new violations. ✅

---

## Test Results

| Suite | Result | Details |
|-------|--------|---------|
| Unit tests (F-00077 specific) | 7 passed, 2 skipped | Skipped tests require DB-level ENUM/constraint that only integration tests can verify |
| Integration tests (F-00077) | 7 passed | All migration, ENUM, indexes, FK cascade, PK auto-generation, unique partial index tests pass |
| Full unit suite | 2493 passed, 4 skipped, 5 xfailed, 1 xpassed | Pre-existing xpassed in `tests/unit/test_batch_planner.py`; not related to F-00077 |

**Coverage**: Integration tests run against testcontainers only (3.47% coverage is expected — most orch code is not exercised by migration-only tests). Unit tests cover the ORM model behavior directly.

---

## Findings

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00077",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2493 unit passed (incl. F-00077 unit), 7 integration passed (F-00077)",
  "notes": "All S01 files pass lint/format. Migration is correct (down_revision verified against alembic head, upgrade/downgrade order verified, cascade deletes present, partial indexes correct, ENUM strategy avoids SQLAlchemy auto-management). ORM classes follow SQLAlchemy 2.0 Mapped[] style and avoid DeclarativeBase.metadata collision via message_metadata attribute. tiktoken in dependencies. Tests use testcontainers with psycopg2 replacement and FTS SQL run after create_all. Skipped unit tests (ENUM constraint, unique partial index) are correctly justified — the integration test suite covers the DB-level enforcement."
}
```

---

## Conclusion

**S01 (database-impl) passes review.** The implementation correctly establishes the persistence layer for F-00077. No mandatory fixes. Proceed to S03 (backend-impl).