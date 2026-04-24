# CR-00019_S01_Database_prompt

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
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

Testcontainers spun up by pytest fixtures are allowed (they self-destruct via Ryuk).
Read-only introspection (`docker ps`, `docker inspect`, `docker logs`) is allowed.
Invoking `./ai-core.sh` or `make` targets is allowed.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade`, `alembic downgrade`, or `alembic stamp` against the
live orchestration DB (port 5433). Your job is to **write** the migration file.
The daemon applies it on merge.

Allowed: `alembic revision --autogenerate -m "..."`, `alembic history/current/show`
(read-only), and migration execution inside testcontainer fixtures.

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md` — design document (read Impact Analysis, Data Migration, and AC13)
- `orch/db/models.py` — current `ProjectOssJobStatus`, `ProjectOssJob`, `OssFinding` definitions
- `orch/db/migrations/versions/824e6e6f34ee_add_oss_compliance_tables.py` — reference for the enum-create pattern
- `docs/IW_AI_Core_Database_Schema.md` — schema documentation to update

## Output Files

- New migration under `orch/db/migrations/versions/` (autogenerate a timestamped filename)
- Updated `orch/db/models.py`
- Updated `docs/IW_AI_Core_Database_Schema.md`
- `ai-dev/work/CR-00019/reports/CR-00019_S01_Database_report.md`

## Context

You are implementing the database layer of **CR-00019**. The CR introduces an awaiting-review lifecycle for OSS Prepare jobs and adds a per-finding rationale field. Read the design document's Impact Analysis section first — it specifies exactly which columns and enum values to add and the reversibility rules.

## Requirements

### 1. Model updates in `orch/db/models.py`

- **`ProjectOssJobStatus` enum** — add two new values in this exact order (after existing values to preserve PG enum ordering):
  - `awaiting_review = "awaiting_review"`
  - `discarded = "discarded"`
- **`ProjectOssJob` mapped class** — add four nullable TEXT columns with short `comment=` strings:
  - `base_sha` — "Main branch HEAD sha at the time Prepare started (for moved-main detection)"
  - `branch_name` — "Prep branch created in the worktree, e.g. iw-oss-publish/prep-<job_id>"
  - `commit_sha` — "HEAD of the prep branch after auto-commit"
  - `files_changed_summary` — "Output of git diff --stat base_sha..commit_sha"
- **`OssFinding` mapped class** — add one nullable TEXT column:
  - `rationale` — "Per-check rationale paragraph explaining why this check exists"

Do not change the existing column order; append the new columns at the end of each class's column block.

### 2. Alembic migration

Create the migration file via `uv run alembic revision --autogenerate -m "CR-00019 oss prepare awaiting review lifecycle"`. Then **edit the generated file** to ensure:

- **Enum values** are added with `op.execute()` statements using `ALTER TYPE ... ADD VALUE IF NOT EXISTS`. `ADD VALUE` cannot run inside a transaction on some PG versions — use one of these patterns (match what this repo already does; inspect existing migrations before picking):
  - `with op.get_context().autocommit_block(): op.execute("ALTER TYPE project_oss_job_status ADD VALUE IF NOT EXISTS 'awaiting_review'")` — preferred.
  - If autocommit_block is unavailable, set `transactional = False` at module level and use plain `op.execute(...)`.
- **Column additions** use `op.add_column("project_oss_job", sa.Column(...))` and `op.add_column("oss_finding", sa.Column(...))`, all nullable, no server_default, no backfill required.
- **Down-migration**:
  - `op.drop_column(...)` for all five new columns (reverse order).
  - For the enum values: write a comment in the down-migration explaining that Postgres does not support `DROP VALUE` and that rollback leaves the values in place. Do NOT attempt `ALTER TYPE ... DROP VALUE` or `DROP TYPE`; they will either fail or destroy in-use data.

Verify the migration runs forward and backward in a testcontainer before reporting completion. Use `make test-integration` or write a short migration-specific integration test (see S11 — but at this step, at minimum, exercise the migration locally against a testcontainer by running any existing test that uses `Base.metadata.create_all()` + the migration fixture path).

### 3. Update `docs/IW_AI_Core_Database_Schema.md`

- Extend the `project_oss_job_status` enum row to include the two new values.
- Extend the `project_oss_job` DDL block to include the four new columns (with comments).
- Extend the `oss_finding` DDL block to include the `rationale` column.
- Add a brief paragraph under the OSS section noting the awaiting-review lifecycle (queued → running → awaiting_review → complete/discarded/error).

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md` for:
- SQLAlchemy 2.0 `Mapped[]` declarative style, `psycopg` v3 (NOT psycopg2).
- Testcontainer-only tests. `FTS_FUNCTION_SQL` and `FTS_TRIGGER_SQL` must be re-run after `Base.metadata.create_all()` in test fixtures — if your models change, verify existing fixtures still apply cleanly.
- `DaemonEvent.metadata` is aliased to `event_metadata` — SQLAlchemy reserves `metadata`. Confirm none of your new columns collide with SQLAlchemy reserved names.

## TDD Requirement

The bulk of the test work lives in S11. For this step, TDD on the migration itself:

1. **RED**: Write a minimal integration test (one file under `tests/integration/`) that spins up a testcontainer, applies the migration, and asserts: enum values present, new columns exist on both tables, types match. Run it — it must fail before your changes.
2. **GREEN**: Make the model and migration changes so the test passes.
3. **REFACTOR**: Tidy naming, comments, and ensure the migration is idempotent (applying twice is a no-op).

## Test Verification (NON-NEGOTIABLE)

Before reporting completion:
1. `make test-unit` — zero failures.
2. `make lint` — clean.
3. `uv run mypy orch/` — clean.
4. Run the migration integration test you wrote — passes.
5. Do NOT run `make test-integration` in its entirety if it's slow; the QV gate at S17 does that. But DO run your new migration test end-to-end.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00019",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<timestamp>_cr_00019_oss_prepare_awaiting_review_lifecycle.py",
    "docs/IW_AI_Core_Database_Schema.md",
    "tests/integration/test_cr_00019_migration.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Confirm the enum-add-value pattern used (autocommit_block vs transactional=False) and why."
}
```
