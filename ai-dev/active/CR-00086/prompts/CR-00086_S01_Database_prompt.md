# CR-00086_S01_Database_prompt

**Work Item**: CR-00086 -- Self-dashboarding of test health
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

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in THIS step is to WRITE the migration FILE. The daemon will
apply it as part of the merge pipeline (pre-merge dry-run against a
testcontainer at S02 via `make migration-check`, post-merge apply to
the live DB). If the migration is broken, the daemon will refuse to
merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00086 --json`.
- `ai-dev/active/CR-00086/CR-00086_CR_Design.md` -- Design document (read the Database Changes section + AC1)
- `orch/db/models.py` -- existing models (study FK and `doc=` patterns of nearby tables)
- `orch/db/migrations/versions/` -- existing revisions (study the most recent one for style)
- `tests/integration/data_layer/test_migration_round_trip.py` -- if it exists, follow its parametrised pattern

## Output Files

- `ai-dev/work/CR-00086/reports/CR-00086_S01_Database_report.md` -- Step report
- Migration file under `orch/db/migrations/versions/<rev>_add_test_health_snapshots_table.py`
- Model addition in `orch/db/models.py`

## Context

You are implementing the **Database** step of **CR-00086: Self-dashboarding of test health**. This step adds a single new table (`test_health_snapshots`) and the matching SQLAlchemy ORM model. The next step (S02) runs `make migration-check` to validate your work in a testcontainer.

Read `CLAUDE.md` and `tests/CLAUDE.md` for project-specific patterns and conventions before starting.

## Requirements

### 1. Alembic migration

Run `uv run alembic revision -m "add_test_health_snapshots_table"` (autogenerate is fine if you've added the model first; otherwise hand-write the `op.create_table` call). The migration MUST:

- Create table `test_health_snapshots` with columns:
  - `id BIGSERIAL PRIMARY KEY`
  - `project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE`
  - `ts TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `metric TEXT NOT NULL`
  - `value DOUBLE PRECISION NOT NULL`
  - `meta JSONB NOT NULL DEFAULT '{}'::jsonb`
- Create index `ix_test_health_snapshots_project_metric_ts` on `(project_id, metric, ts DESC)`.
- Implement `downgrade()` to drop the index and the table (in that order).

**IMPORTANT** (per `CLAUDE.md` hard rule): commit the revision file to git in this step. An uncommitted revision file in a worktree causes `alembic upgrade head` to die with `Can't locate revision identified by '<rev>'` (I-00075 / I-00076).

### 2. SQLAlchemy model

Add `TestHealthSnapshot` to `orch/db/models.py` matching the migration's columns. Every column MUST carry a `doc=` string (project testing-skill rule). Add the relationship `project = relationship("Project")` (no back_populates needed unless you want to add `test_health_snapshots` on Project — optional). Place the class alphabetically among siblings.

### 3. Round-trip fixture

If `tests/integration/data_layer/test_migration_round_trip.py` uses a parametrised list of `(model_class, sample_row_kwargs)` tuples, add the new shape. If not, add a small test that inserts and reads back a `TestHealthSnapshot` row in the testcontainer.

## Project Conventions

Read the project's `CLAUDE.md` for:

- SQLAlchemy ORM style (`Mapped`, `mapped_column`, `doc=` strings)
- The CR-00021 migration-rebase contract (daemon applies, agents only generate)
- Test fixtures (`tests/conftest.py` testcontainer pattern; never connect tests to port 5433)
- The `event_metadata` vs `metadata` SQLAlchemy reserved-name trap (does NOT affect this table since we use `meta`, but be aware)

Follow all rules defined there exactly. When in doubt, match existing models like `DocGenerationJob` or `CodeIndexJob` for the closest precedent.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Before writing the migration, add the round-trip fixture/test row referenced above. Run `uv run pytest tests/integration/data_layer/test_migration_round_trip.py -v -k test_health_snapshots` and capture the failure — it MUST be a `NoSuchTableError` or `UndefinedTable`, NOT an import/collection error.
2. **GREEN**: Write the migration and model. Re-run; the test passes.
3. **REFACTOR**: Tidy `doc=` strings; ensure column order matches between migration and model.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order and fix any issues:

1. `make format` — auto-fixes formatting; re-stage if it changes anything.
2. `make typecheck` — zero errors on touched files.
3. `make lint` — zero errors.

Populate the `preflight` object in your result contract.

## Test Verification (NON-NEGOTIABLE)

After implementation, verify only your own changes:

- `uv run pytest tests/integration/data_layer/test_migration_round_trip.py -v` (or whichever file you extended)

Do NOT run the full suite — S12 and S13 are the QV gates for that.

## Migration Verification (Database step — NON-NEGOTIABLE)

After writing the migration, you MUST run **`make migration-check`** before reporting completion. This spins a fresh testcontainer Postgres, runs upgrade from base, asserts the resulting schema matches `Base.metadata.create_all()` (catches drift), and round-trips through downgrade -> upgrade.

If `make migration-check` fails, fix the migration file (or the model) so both halves agree.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<rev>_add_test_health_snapshots_table.py",
    "tests/integration/data_layer/test_migration_round_trip.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/integration/data_layer/test_migration_round_trip.py::test_health_snapshots — sqlalchemy.exc.NoSuchTableError: test_health_snapshots  // RED captured before adding the model+migration",
  "blockers": [],
  "notes": ""
}
```
