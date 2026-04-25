# F-00062_S01_Database_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
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

Allowed exceptions (read-only): `docker ps`, `docker inspect`, `docker logs`. Plus testcontainers via pytest fixtures.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

You write the migration FILE only. You do NOT run `alembic upgrade`/`downgrade`/`stamp` against the live orch DB on port 5433. Allowed: `alembic revision --autogenerate`, `alembic history|current|show`, and migrations inside testcontainer pytest fixtures.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## Input Files

- `ai-dev/active/F-00062/F-00062_Feature_Design.md` — Design document (read FIRST)
- `orch/db/models.py` — `BatchItem` model (line ~900) and `BatchItemStatus` enum (line ~141)
- `docs/IW_AI_Core_Database_Schema.md` — schema documentation to update

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S01_Database_report.md` — step report

## Context

You are implementing the schema changes for **per-worktree container isolation**. Three nullable columns are added to `batch_items` so the daemon can persist the docker-compose stack metadata: the discovered DB host port, the discovered app host port, and the absolute path to the rendered compose file.

Read the design document — Sections "Database Changes" and "Acceptance Criteria → AC1, AC4, AC5" describe what these columns are used for and why all three must be NULL together (Invariant #6).

## Requirements

### 1. Add three nullable columns to the `BatchItem` ORM model

In `orch/db/models.py`, on the `BatchItem` class:

```python
worktree_db_port: Mapped[int | None] = mapped_column(
    nullable=True,
    comment="Discovered host port for the per-worktree Postgres container; NULL when the project runs in legacy mode (no iw-config/)"
)
worktree_app_port: Mapped[int | None] = mapped_column(
    nullable=True,
    comment="Discovered host port for the per-worktree app server container; NULL when no app service is declared or in legacy mode"
)
worktree_compose_path: Mapped[str | None] = mapped_column(
    nullable=True,
    comment="Absolute filesystem path to the rendered docker-compose-<id>.yml; NULL in legacy mode. Used by the reaper and daemon-restart re-attach logic."
)
```

Match the existing column ordering and the docstring style used elsewhere in `BatchItem` (see existing `worktree_path` column for reference).

### 2. Verify `BatchItemStatus.setup_failed` exists

The design's AC6 and AC8 transition `BatchItem.status` to `setup_failed`. Audit the `BatchItemStatus` enum in `orch/db/models.py`. If `setup_failed` is NOT already a value:

- Add it to the Python enum
- Include the PG enum addition in your Alembic migration via `op.execute("ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'setup_failed'")` inside an autocommit block (see CR-00019 / CR-00021 precedent for `ALTER TYPE` mechanics — must run outside a transaction)

If `setup_failed` already exists, document that in your report and skip this part.

### 3. Generate one additive Alembic migration

```bash
uv run alembic revision --autogenerate -m "F-00062 add worktree compose stack columns to batch_items"
```

Review the generated file. It should contain ONLY:
- `op.add_column('batch_items', sa.Column('worktree_db_port', sa.Integer(), nullable=True))`
- `op.add_column('batch_items', sa.Column('worktree_app_port', sa.Integer(), nullable=True))`
- `op.add_column('batch_items', sa.Column('worktree_compose_path', sa.Text(), nullable=True))`
- (Optionally) the `ALTER TYPE` for `setup_failed` if needed per Requirement 2

Add a clear module docstring referencing F-00062. The `downgrade()` function drops the three columns; if you added the enum value, leave the enum value in place on downgrade (Postgres cannot drop enum values — same trade-off as CR-00019/CR-00021; document this in the docstring).

**Do NOT run `alembic upgrade head` against the live orch DB.** The daemon will apply the migration as part of the merge pipeline.

### 4. Update `docs/IW_AI_Core_Database_Schema.md`

In the `batch_items` section, add the three new columns with descriptions matching the ORM `comment=` strings. Note that all three are NULL for legacy worktrees (projects without `ai-dev/iw-config/`). If you added `setup_failed`, list it in the `batch_item_status` enum table.

## Project Conventions

- Read `CLAUDE.md` and `orch/CLAUDE.md` for ORM patterns (SQLAlchemy 2.0 `Mapped[]`, psycopg v3, append-only tables — these are not append-only, just additive columns)
- Existing column ordering and style: study `worktree_path` and adjacent columns on `BatchItem`

## TDD Requirement

Schema-only step. The repo's existing convention is **flat under `tests/unit/`** (e.g., `tests/unit/test_safe_migrate.py`, `tests/unit/test_batch_manager.py`); model-level tests currently live in `tests/integration/test_models.py` (testcontainer-backed). Add a unit test at `tests/unit/test_batch_item_columns.py` (new flat file — no `tests/unit/db/` directory exists in this repo) that:

1. Asserts `BatchItem.worktree_db_port`, `worktree_app_port`, `worktree_compose_path` are present, nullable, and have the expected types (Integer, Integer, Text).
2. Asserts that all three default to None on a freshly-constructed BatchItem.

Follow RED → GREEN → REFACTOR.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-unit` — must pass
2. Run `make lint` and `make quality` — must pass
3. Verify the migration file is syntactically valid by running `uv run alembic check` (read-only)
4. Do NOT report `tests_passed: true` unless all unit tests pass

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<hash>_f_00062_*.py",
    "docs/IW_AI_Core_Database_Schema.md",
    "tests/unit/test_batch_item_columns.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Whether setup_failed enum value pre-existed or was added"
}
```
