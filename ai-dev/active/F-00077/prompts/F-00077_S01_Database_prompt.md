# F-00077_S01_Database_prompt

**Work Item**: F-00077 -- Code chat conversation memory with persistence and query rewriting
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a
blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live orch
DB (port 5433). Your job in this step is to WRITE the migration FILE.
The daemon applies it during the merge pipeline.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

If the migration is broken, the daemon will refuse to merge the batch.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00077 --json`
- `ai-dev/active/F-00077/F-00077_Feature_Design.md` — design (sections: Database Changes, Acceptance Criteria AC6, Invariants 1-3, Boundary Behavior)
- `orch/db/models.py` — current ORM. Reference patterns:
  - `CodeIndexJob` at line 1475 — single-column `id` PK, `project_id` regular column, status string (NOT a Postgres ENUM)
  - `DocGenerationJob` at line 1322 — same shape
  - Composite-PK pattern (`WorkItem` at line 403) is NOT used for chat tables
- `orch/db/migrations/versions/` — existing history (run `alembic history` to find current head)

## Output Files

- `ai-dev/active/F-00077/reports/F-00077_S01_Database_report.md` — step report
- `orch/db/migrations/versions/<rev>_F-00077_chat_conversations.py` — new alembic revision
- `orch/db/models.py` — adds `ChatConversation`, `ChatMessage`, `ChatSummarizationJob` ORM classes
- `pyproject.toml` + `uv.lock` — adds `tiktoken` direct dependency
- Two new test files (see Tests section below)

## Context

You are creating the persistence layer for the Code chat memory feature. Read the design FIRST: sections "Description", "Database Changes", "Acceptance Criteria AC6/AC8", and "Invariants 1-3" set the contract. Then read `orch/CLAUDE.md` (SQLAlchemy 2.0 / Alembic conventions, append-only tables) and `tests/CLAUDE.md` (testcontainer rules, FTS triggers).

## Requirements

### 1. Postgres ENUM for `chat_messages.role`

Create the ENUM `chat_message_role` with values `('user', 'assistant', 'system')`. Use `postgresql.ENUM` with `create_type=False` if you create it manually inside `op.execute(...)`, OR rely on alembic's auto-emission if you go via the SQLAlchemy `Enum(..., name='chat_message_role')` route. Either is fine — pick one and be consistent. The `downgrade()` MUST drop the ENUM after dropping the table that uses it.

### 2. ORM classes in `orch/db/models.py`

Add three classes at the end of the file (after `CodeIndexJob`). Use SQLAlchemy 2.0 `Mapped[]` style consistent with the rest of the file. Composite PKs are NOT used here; each table has a single `id TEXT PK` (`gen_random_uuid()::text`).

**`ChatConversation`** (`__tablename__ = "chat_conversations"`):

```python
id              Mapped[str]              # PK, server_default gen_random_uuid()::text
project_id      Mapped[str]              # NOT NULL, FK semantics maintained at app layer (matches existing job tables)
session_id      Mapped[str]              # NOT NULL — browser session cookie
module_path     Mapped[str | None]       # nullable; snapshot of the first turn's module
context_level   Mapped[str]              # NOT NULL DEFAULT 'architecture' — "architecture" | "module"
title           Mapped[str | None]       # nullable; first user question, truncated to 80 chars
rolling_summary Mapped[str | None]       # nullable; populated by ChatSummarizationJob
summary_through_message_id  Mapped[str | None]  # nullable; FK to chat_messages.id (no ON DELETE — handled by CASCADE on conversation delete)
created_at      Mapped[datetime]         # server_default now()
last_active_at  Mapped[datetime]         # server_default now()
archived_at     Mapped[datetime | None]  # nullable
```

Indexes:
- `idx_chat_conversations_project_session_recent` ON `(project_id, session_id, last_active_at DESC) WHERE archived_at IS NULL`. Use `Index(..., postgresql_where=text("archived_at IS NULL"))`.

`__table_args__`: include the partial index above and a `comment` describing the table.

**`ChatMessage`** (`__tablename__ = "chat_messages"`):

```python
id              Mapped[str]   # PK
conversation_id Mapped[str]   # NOT NULL, FK chat_conversations(id) ON DELETE CASCADE
role            Mapped[str]   # NOT NULL, mapped to chat_message_role ENUM
content         Mapped[str]   # NOT NULL, Text (no upper bound — caller validates)
token_count     Mapped[int]   # NOT NULL DEFAULT 0
metadata        Mapped[Any]   # JSONB NOT NULL DEFAULT '{}'::jsonb
                              # ⚠️ SQLAlchemy reserves `metadata` on DeclarativeBase. Use the
                              # column name `metadata` in DDL but the Python attribute name
                              # `message_metadata` (mirrors DaemonEvent.event_metadata pattern
                              # — see orch/CLAUDE.md "Gotcha")
created_at      Mapped[datetime]
```

Foreign key: declare via `mapped_column(..., ForeignKey("chat_conversations.id", ondelete="CASCADE"))`.

Index: `idx_chat_messages_conversation_created` ON `(conversation_id, created_at)`.

Append-only enforcement: this is a project convention (no DB constraint). Document in the column comment that direct UPDATE is forbidden EXCEPT to set `metadata.error=true` within the same transaction as INSERT (see design Boundary Behavior — stream-disconnected case).

**`ChatSummarizationJob`** (`__tablename__ = "chat_summarization_jobs"`):

Mirror `CodeIndexJob` (line 1475) shape, with these columns:

```python
id                          Mapped[str]   # PK
conversation_id             Mapped[str]   # NOT NULL, FK chat_conversations(id) ON DELETE CASCADE
status                      Mapped[str]   # NOT NULL DEFAULT 'queued' — 'queued|running|completed|failed|cancelled'
messages_summarized         Mapped[int]   # NOT NULL DEFAULT 0
summary_through_message_id  Mapped[str | None]  # nullable
error_message               Mapped[str | None]
triggered_at                Mapped[datetime]
started_at                  Mapped[datetime | None]
completed_at                Mapped[datetime | None]
created_at                  Mapped[datetime]
updated_at                  Mapped[datetime]
```

Indexes:
- `idx_chat_summarization_jobs_status` ON `(status, triggered_at)` — used by daemon poller
- `uq_chat_summarization_jobs_one_in_flight` UNIQUE ON `(conversation_id) WHERE status IN ('queued', 'running')` — enforces invariant 2. Use `Index(..., unique=True, postgresql_where=text("status IN ('queued', 'running')"))`.

### 3. Alembic migration

Generate with:
```bash
uv run alembic revision --autogenerate -m "F-00077 chat conversations memory"
```

The autogenerate output WILL contain noise (FTS-trigger DDL drift, comment-only tweaks on unrelated tables). Hand-trim to ONLY:

- `op.execute("CREATE TYPE chat_message_role AS ENUM ('user', 'assistant', 'system')")` (top of `upgrade()`).
- `op.create_table("chat_conversations", ...)` with all columns + the partial index (`op.create_index(..., postgresql_where=sa.text("archived_at IS NULL"))`).
- `op.create_table("chat_messages", ...)` with FK + the regular index.
- `op.create_table("chat_summarization_jobs", ...)` with both indexes.
- `downgrade()` drops in reverse order: `chat_summarization_jobs`, `chat_messages`, `chat_conversations`, then `DROP TYPE chat_message_role`.

Do NOT touch any FTS triggers, existing tables, or unrelated indexes. If autogenerate proposes them, delete them.

### 4. tiktoken dependency

```bash
uv add tiktoken
```

This is consumed by S03 (backend) for `chat_messages.token_count` computation. Pin the resolved version range as auto-determined by `uv lock` — document the exact version in your report.

### 5. Tests

Add tests under `tests/unit/db/`:

- `tests/unit/db/test_chat_conversation_model.py`:
  - `test_chat_conversation_default_archived_at_is_none` — insert without specifying, assert NULL.
  - `test_chat_conversation_default_context_level_is_architecture`.
  - `test_chat_conversation_metadata_round_trip` — store + read back. (Note: `chat_conversations` does not have a metadata column; this is for `chat_messages`.)
  - `test_partial_index_excludes_archived` — insert two rows, archive one, query the index-backed predicate (`SELECT ... WHERE archived_at IS NULL ORDER BY last_active_at DESC`) and assert ordering + exclusion.

- `tests/unit/db/test_chat_message_model.py`:
  - `test_chat_message_role_enum_rejects_invalid` — INSERT with `role='moderator'` raises `IntegrityError`/`DataError`.
  - `test_chat_message_metadata_default_empty_dict`.
  - `test_chat_message_python_attribute_is_message_metadata` — `getattr(msg, "message_metadata") is not None`, AND `getattr(msg, "metadata", None)` returns the SQLAlchemy `MetaData` (the inherited class attribute, NOT the column). This guards against a future refactor accidentally renaming the Python attribute.
  - `test_cascade_delete_on_conversation` — delete the conversation, assert messages are gone.

- `tests/unit/db/test_chat_summarization_job_model.py`:
  - `test_unique_partial_in_flight_constraint` — insert one with `status='queued'`, attempt a second for the same conversation_id with `status='running'`, expect `IntegrityError`. Then update the first to `status='completed'` and re-attempt — should succeed.
  - `test_default_status_is_queued`.

Use the `db_session` testcontainer fixture per `tests/CLAUDE.md`. Replace `psycopg2://` with `psycopg://`. Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` (these tables don't have FTS but the project-wide fixture expects it).

Add an integration test `tests/integration/db/test_F00077_migration.py`:
- Spins up a fresh testcontainer at the prior head, runs `alembic upgrade head`, asserts: the three tables exist; the ENUM exists; the unique partial index is present (query `pg_indexes`); `Base.metadata` reflects them.

## Project Conventions

Read `orch/CLAUDE.md` and `tests/CLAUDE.md`. Specifically:

- SQLAlchemy 2.0 `Mapped[]` style.
- psycopg v3 (NOT psycopg2). Replace test URLs.
- `JSONB` defaults via `text("'{}'::jsonb")` (NOT `default=lambda: {}`).
- Append-only convention is enforced by code review, not DB constraints.
- Indexes named `idx_<table>_<column(s)>`; unique indexes `uq_<table>_<column(s)>`.

## TDD Requirement

Follow TDD: write the unit tests (RED) before adding the column / table to `models.py` (GREEN). For the migration, write `test_F00077_migration.py` first against a fresh testcontainer; it must fail because the migration doesn't exist; then write the migration.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fix and re-stage.
2. `make typecheck` — zero errors involving the files you touched.
3. `make lint` — zero errors.

## Test Verification

1. `make test-unit` — fast.
2. `make test-integration` — for the migration test.
3. Do NOT report `tests_passed: true` unless ALL pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<rev>_F-00077_chat_conversations.py",
    "pyproject.toml",
    "uv.lock",
    "tests/unit/db/test_chat_conversation_model.py",
    "tests/unit/db/test_chat_message_model.py",
    "tests/unit/db/test_chat_summarization_job_model.py",
    "tests/integration/db/test_F00077_migration.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "tiktoken pinned at <version>; alembic head was <rev>"
}
```
