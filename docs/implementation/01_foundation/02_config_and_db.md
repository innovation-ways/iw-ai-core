# Step 02: Configuration, Database Models & Migration

## Context

You are building IW AI Core. Step 01 created the project skeleton. Now implement the configuration system, all SQLAlchemy models, and the Alembic initial migration.

Read these documents:
- `IW_AI_Core_Database_Schema.md` — complete DDL, ENUMs, indexes, triggers, state machines
- `IW_AI_Core_Tech_Stack.md` — section 8 (configuration), section 4.4 (database test fixtures)

## Task

### 1. Configuration (`orch/config.py`)

Implement configuration loading:
- Load `.env` via `python-dotenv` from the repo root
- Build DB URL from individual env vars (IW_CORE_DB_HOST, IW_CORE_DB_PORT, etc.)
- Dataclass or named tuple for `DaemonConfig` with all config values
- Fail fast with clear error if required env vars are missing
- NO hardcoded ports, URLs, or credentials anywhere

### 2. Database Models (`orch/db/models.py`)

Implement ALL SQLAlchemy 2.0 models (sync, Mapped[] style) for:
- `Project` — id (TEXT PK), display_name, repo_root, dev_clone, config (JSONB), enabled, registered_at, updated_at
- `IdSequence` — composite PK (project_id, prefix), next_number
- `WorkItem` — composite PK (project_id, id), type (ENUM), status (ENUM), phase (ENUM), all Tier 1 columns (design_doc_content, design_doc_search, summary), all Tier 2 columns (archive_path, archive_size_bytes, archived_at), timestamps
- `WorkflowStep` — SERIAL PK, FK to WorkItem, step_number, step_id, agent_label, step_type (ENUM), status (ENUM), report_content (Tier 1), timestamps
- `StepRun` — SERIAL PK, FK to WorkflowStep, run_number, status (ENUM), all process control columns (pid, pid_alive, command, worktree_path, cli_tool, last_heartbeat, timeout_secs, error_message), output columns, timestamps
- `FixCycle` — SERIAL PK, FK to WorkflowStep, cycle_number, trigger_type (ENUM), status (ENUM), timestamps
- `Batch` — composite PK (project_id, id), status (ENUM), max_parallel, auto_publish, timestamps
- `BatchItem` — SERIAL PK, FKs to Batch and WorkItem, execution_group, status (ENUM), pid, worktree_info (JSONB), merge_info (JSONB), timestamps
- `MigrationLock` — project_id PK, current_holder, branch, locked_at, head_revision
- `DaemonEvent` — SERIAL PK, project_id, event_type, entity_id, message, metadata (JSONB), created_at

Use PostgreSQL ENUMs (via `sqlalchemy.Enum` with `create_type=True`). Use the exact enum values from the Database Schema doc.

Add all indexes from the DDL (including the partial index on step_runs and the GIN index on design_doc_search).

Add `comment=` on every `mapped_column()` matching the DDL comments.

### 3. Session Factory (`orch/db/session.py`)

- `create_engine()` from config DB URL
- `sessionmaker()` bound to the engine
- `get_session()` context manager that yields a session and commits/rollbacks

### 4. Alembic Setup

- Initialize Alembic: configure `env.py` to read DB URL from `orch.config`
- Generate initial migration from models
- The migration MUST create the FTS trigger (`work_items_fts_update`) — add it as a raw SQL `op.execute()` in the migration

### 5. Tests

Write tests FIRST (TDD):

**Unit tests** (`tests/unit/test_config.py`):
- Test: missing required env var raises clear error
- Test: all defaults are sensible
- Test: DB URL built correctly from components

**Integration tests** (`tests/integration/conftest.py`):
- Implement the testcontainer fixtures from Tech Stack doc section 4.4:
  - `pg_container` (session-scoped) — starts PostgreSQL testcontainer on random port
  - `db_engine` (session-scoped) — creates engine + all tables via `Base.metadata.create_all()`
  - `db_session` (function-scoped) — transactional session with rollback after each test
- Tests MUST NOT load `.env` or connect to the live database

**Integration tests** (`tests/integration/test_models.py`):
- Test: all models can be created (insert a row, query it back)
- Test: ENUM constraints reject invalid values
- Test: composite PKs work (same ID in different projects)
- Test: cascade deletes work (delete project → all children deleted)
- Test: FTS trigger updates tsvector when design_doc_content changes

## Acceptance Criteria

- [ ] `make db-up && make db-migrate` creates all 10 tables, all ENUMs, all indexes, the FTS trigger
- [ ] `make test-unit` passes (config tests)
- [ ] `make test-integration` passes (model tests against testcontainer)
- [ ] `make quality` passes (ruff + mypy clean)
- [ ] Tests run while the live PostgreSQL container is running on its port — zero interference
