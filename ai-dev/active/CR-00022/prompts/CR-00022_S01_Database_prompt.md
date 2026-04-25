# CR-00022_S01_Database_prompt

**Work Item**: CR-00022 -- OSS Compliance — per-finding fixes, table+modal UX, no branch creation
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

Allowed exceptions: testcontainers spun up by pytest fixtures; read-only `docker ps/inspect/logs`; invoking `./ai-core.sh` or `make`. If your task seems to require a prohibited command, STOP and raise a blocker. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live orchestration DB. Your job in a Database step is to WRITE the migration FILE. The daemon applies it post-merge after a testcontainer dry-run.

Allowed for agents: `alembic revision --autogenerate -m "..."`, `alembic history|current|show`, running migrations inside testcontainer fixtures.

## Input Files

- `ai-dev/active/CR-00022/CR-00022_CR_Design.md` — design document (read first)
- `orch/db/models.py` — current ORM definitions
- `docs/IW_AI_Core_Database_Schema.md` — schema reference

## Output Files

- New: `orch/db/migrations/versions/{revision_id}_cr_00022_oss_redesign_drop_prepare_publish.py`
- Modified: `orch/db/models.py`
- Modified: `docs/IW_AI_Core_Database_Schema.md`
- `ai-dev/active/CR-00022/reports/CR-00022_S01_Database_report.md` — step report

## Context

You are implementing the database layer of CR-00022. This step prunes Postgres enums (drops `prepare`/`publish` from `project_oss_job_kind`, drops `make_oss`/`publish` from `ossscan_mode`, drops `awaiting_review`/`discarded` from `project_oss_job_status`), drops four columns from `project_oss_job`, adds a new `auto_apply_safe BOOLEAN NOT NULL DEFAULT false` column on `oss_finding`, and adds a new enum value `fix` to `project_oss_job_kind`. The migration is **hard and irreversible** (deletes historical rows referencing the dropped enum values).

Read `CLAUDE.md`, `orch/CLAUDE.md`, and the design document before writing any code.

## Requirements

### 1. Pre-migration data deletion

Before any enum recreate, the migration MUST delete:
- All rows in `project_oss_job` where `kind in ('prepare','publish')`.
- All rows in `oss_scan` where `mode in ('make_oss','publish')` (their cascading `oss_finding` and `oss_tool_run` rows go via existing `ondelete='CASCADE'`).
- All rows in `project_oss_job` where `status in ('awaiting_review','discarded')` (defensive — should already be gone after the kind delete).

### 2. Enum recreates

Postgres does not support dropping enum values directly. Use the recreate-cast-drop pattern for each enum:

1. Create new enum type with the new value set (e.g., `project_oss_job_kind_new` containing `scan, install, fix`).
2. Alter the column(s) using the enum to TEXT.
3. Drop the old enum.
4. Recreate the enum under the original name.
5. Alter the column back to the new enum via `USING column::project_oss_job_kind`.

Do this for: `project_oss_job_kind` (drop `prepare`,`publish`; add `fix`), `ossscan_mode` (drop `make_oss`,`publish`; final values: `scan`), `project_oss_job_status` (drop `awaiting_review`,`discarded`; final values: `queued`,`running`,`complete`,`error`,`cancelled`).

### 3. Column drops

Drop the following columns from `project_oss_job`: `worktree_path`, `branch_name`, `commit_sha`, `files_changed_summary`. Order matters only if downgrade is implemented — for this hard migration, downgrade is NOT REQUIRED. Implement `def downgrade()` as `raise NotImplementedError("CR-00022 is a hard migration; restore from backup to revert")`.

### 4. New column on `oss_finding`

Add `auto_apply_safe BOOLEAN NOT NULL DEFAULT false`. Existing rows get `false`. ORM model adds the field with `Boolean, nullable=False, server_default=text("false")`.

### 5. ORM updates

Update `orch/db/models.py`:
- `ProjectOssJobKind` enum: remove `prepare`, `publish`; add `fix`.
- `OssScanMode` enum: remove `make_oss`, `publish`. (Consider keeping the enum even with one value to preserve the column, OR removing the column entirely if simpler — recommend keeping for forward-compat.)
- `ProjectOssJobStatus` enum: remove `awaiting_review`, `discarded`.
- `ProjectOssJob` model: remove `worktree_path`, `branch_name`, `commit_sha`, `files_changed_summary` mapped columns. Update class docstring + table comment.
- `OssFinding` model: add `auto_apply_safe: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))`.

Keep relationships, indexes, and FKs intact.

### 6. Schema docs

Update `docs/IW_AI_Core_Database_Schema.md`:
- Update the `project_oss_job` DDL block to reflect dropped columns and pruned enum.
- Update the `oss_finding` DDL block with the new column.
- Update the `oss_scan` DDL block to reflect pruned mode enum.
- Add a one-line note in the change-history section pointing at this CR.

### 7. Generate the migration

```bash
uv run alembic revision --autogenerate -m "CR-00022 OSS redesign: drop prepare/publish, add auto_apply_safe"
```

Then **manually edit** the generated file because autogenerate WILL NOT correctly produce enum recreate-cast-drop. The migration body must:

```python
def upgrade() -> None:
    # 1. Pre-delete rows referencing dropped enum values
    op.execute("DELETE FROM project_oss_job WHERE kind IN ('prepare','publish')")
    op.execute("DELETE FROM oss_scan WHERE mode IN ('make_oss','publish')")
    op.execute("DELETE FROM project_oss_job WHERE status IN ('awaiting_review','discarded')")

    # 2. Drop columns from project_oss_job
    op.drop_column("project_oss_job", "files_changed_summary")
    op.drop_column("project_oss_job", "commit_sha")
    op.drop_column("project_oss_job", "branch_name")
    op.drop_column("project_oss_job", "worktree_path")

    # 3. Add column to oss_finding
    op.add_column(
        "oss_finding",
        sa.Column("auto_apply_safe", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # 4. Recreate project_oss_job_kind enum (drop prepare/publish, add fix)
    op.execute("CREATE TYPE project_oss_job_kind_new AS ENUM ('scan','install','fix')")
    op.execute(
        "ALTER TABLE project_oss_job ALTER COLUMN kind TYPE project_oss_job_kind_new "
        "USING kind::text::project_oss_job_kind_new"
    )
    op.execute("DROP TYPE project_oss_job_kind")
    op.execute("ALTER TYPE project_oss_job_kind_new RENAME TO project_oss_job_kind")

    # 5. Recreate ossscan_mode enum (drop make_oss/publish)
    op.execute("CREATE TYPE ossscan_mode_new AS ENUM ('scan')")
    op.execute(
        "ALTER TABLE oss_scan ALTER COLUMN mode TYPE ossscan_mode_new "
        "USING mode::text::ossscan_mode_new"
    )
    op.execute("DROP TYPE ossscan_mode")
    op.execute("ALTER TYPE ossscan_mode_new RENAME TO ossscan_mode")

    # 6. Recreate project_oss_job_status enum (drop awaiting_review/discarded)
    op.execute(
        "CREATE TYPE project_oss_job_status_new AS ENUM "
        "('queued','running','complete','error','cancelled')"
    )
    op.execute(
        "ALTER TABLE project_oss_job ALTER COLUMN status TYPE project_oss_job_status_new "
        "USING status::text::project_oss_job_status_new"
    )
    op.execute("DROP TYPE project_oss_job_status")
    op.execute("ALTER TYPE project_oss_job_status_new RENAME TO project_oss_job_status")


def downgrade() -> None:
    raise NotImplementedError(
        "CR-00022 is a hard migration; restore from backup to revert"
    )
```

Verify the revision uses the last-applied head as `down_revision`. Use `uv run alembic history` to find it.

### 8. Validate against testcontainer fixture

The integration test fixture (`tests/conftest.py` autouse) runs `Base.metadata.create_all()` followed by FTS triggers. The new `auto_apply_safe` column must materialise. Run `make test-integration -- tests/integration/test_oss_migration.py` to confirm; it MAY fail until S17 updates assertions, but the migration itself must run without exception.

## Project Conventions

Follow `orch/CLAUDE.md` for SQLAlchemy 2.0 sync style, psycopg v3, append-only tables, composite-PK conventions, and Postgres enum naming. Match the existing migration style in `orch/db/migrations/versions/9ef17911f546_*.py` (which previously *added* `awaiting_review`/`discarded`).

## TDD Requirement

This is a schema-only step. Tests for the migration live in `tests/integration/test_oss_migration.py` and `tests/integration/test_project_oss_job_migration.py`; updating those is S17's job. For S01 itself, ensure the autogenerated migration runs in a testcontainer (the conftest fixture exercises it implicitly).

## Output / Report

Write `ai-dev/active/CR-00022/reports/CR-00022_S01_Database_report.md` listing:

- Migration revision ID + filename
- Files modified (paths + diff summary)
- Manual verification: `uv run alembic upgrade head` against a fresh testcontainer (use `IW_CORE_DB_URL` pointing at a throwaway container)
- Open questions / risks for downstream steps

End with one of:

```bash
uv run iw step-done CR-00022 --step S01 --report ai-dev/active/CR-00022/reports/CR-00022_S01_Database_report.md
# OR
uv run iw step-fail CR-00022 --step S01 --reason "<reason>" --report ...
```
