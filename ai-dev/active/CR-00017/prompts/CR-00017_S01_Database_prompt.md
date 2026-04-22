# CR-00017_S01_Database_prompt

**Work Item**: CR-00017 — Daemon-only migration application
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT run `docker`, `docker compose`, `docker-compose`, or any
command that stops/starts/removes containers or volumes. Exceptions:
testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`;
invocations through `./ai-core.sh` or `make`.

See `docs/IW_AI_Core_Agent_Constraints.md` for the full policy.

## ⛔ Migrations are off-limits to apply

You MUST NOT run `alembic upgrade head` or any alembic command that
modifies the live orchestration DB. Your job in this step is to write
a migration FILE. Post-CR-00017 (this very CR), the daemon will apply
it after squash-merge. You write; the daemon applies.

If you feel like you need to apply migrations during development, use
a testcontainer via pytest fixtures (`tests/conftest.py` pattern).

---

## Input Files

- `ai-dev/active/CR-00017/CR-00017_CR_Design.md` — Design (Data Migration section, AC9)
- `orch/db/models.py` — existing ORM patterns (SQLAlchemy 2.0 Mapped[], composite PKs, reserved-word gotchas)
- `orch/db/migrations/versions/` — latest alembic head (will be CR-00014's revision assuming CR-00014 has merged; confirm with `uv run alembic heads`)
- `tests/CLAUDE.md` — FTS triggers, psycopg v3 URL replacement
- `CLAUDE.md`, `orch/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00017/reports/CR-00017_S01_Database_report.md`
- `orch/db/migrations/versions/{hash}_add_pending_migration_log.py` (new)
- `orch/db/models.py` (add `PendingMigrationLog`)
- `tests/integration/test_pending_migration_log_migration.py` (new RED test)

## Context

You're building the audit-log table for CR-00017's 3-phase migration pipeline. The table records every `dry_run`, `apply`, and `rollback` phase the daemon performs. Read the design doc's **Data Migration** section for the exact schema.

## Requirements

### 1. Alembic migration

Chain from the then-current head (probably CR-00014's revision). The migration must create the table exactly per the design doc:

- `id BIGSERIAL PRIMARY KEY`
- `revision TEXT NOT NULL`
- `direction TEXT NOT NULL CHECK (direction IN ('upgrade', 'downgrade'))`
- `phase TEXT NOT NULL CHECK (phase IN ('dry_run', 'apply', 'rollback'))`
- `batch_id BIGINT REFERENCES batches(id) ON DELETE SET NULL`  (nullable — for operator-triggered manual applies with no batch)
- `started_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `completed_at TIMESTAMPTZ`
- `success BOOLEAN`
- `stdout_tail TEXT`
- `stderr_tail TEXT`
- `error_message TEXT`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- Indexes: `(batch_id, started_at DESC)`, `(revision, phase)`
- Table comment: "CR-00017 audit log for daemon-driven migration phases"

Downgrade drops the table. No FKs inbound, no cascading concerns.

**Important**: use `CheckConstraint(name=...)` in the ORM model so alembic can autogenerate clean. Match phrasing to existing models — `MigrationLock` and `TestRun` are good references.

### 2. ORM model

`class PendingMigrationLog(Base)` in `orch/db/models.py`. Typed `Mapped[]` style. Placement near `MigrationLock` and `DaemonEvent` (the other audit/infrastructure tables). Include a relationship to `Batch` (optional; `batch_id` is nullable).

Watch out for: no column named `metadata` (SQLAlchemy reserved — see `DaemonEvent` for the `event_metadata` precedent; not applicable here but re-confirm none of our columns collide).

### 3. RED test

`tests/integration/test_pending_migration_log_migration.py`:

- Spin a testcontainer, apply `alembic upgrade head`, assert: table exists, all columns + types correct, CHECK constraints enforce valid enum values (test by attempting invalid INSERT, expect `IntegrityError`), indexes exist.
- Round trip: `alembic downgrade -1` drops the table; `alembic upgrade head` re-creates it empty.
- FK behavior: insert a row with a valid `batch_id`, then delete the batch, assert the `pending_migration_log.batch_id` becomes NULL (ON DELETE SET NULL).

Follow `tests/CLAUDE.md`: psycopg v3 URL replacement, FTS_FUNCTION_SQL + FTS_TRIGGER_SQL after `create_all()`.

### 4. No side-effect

This table is **append-only audit** — no triggers, no constraints that prevent INSERTs of any valid combination. Do not over-engineer.

## Project Conventions

- Migration file: `from __future__ import annotations`, `from collections.abc import Sequence`, `revision: str = "..."`, `down_revision: str | None = "..."`.
- ORM: typed `Mapped[]`, `server_default=func.now()` for timestamps, no Python-side defaults for DB-timestamp columns.
- Imports grouped per existing convention in `models.py`.

## Migration-lock pre-flight

Before running `alembic revision --autogenerate`:

```bash
uv run iw migration-lock status
```

If stale (held by a dead item), handle per project convention (release with `--force` if the CLI supports it, or escalate as a blocker). Acquire under `CR-00017` at step start; release at step end.

## TDD Requirement

Red → Green → Refactor. Write the test first. Run it, confirm it fails (no table). Then write the migration + model. Run it, confirm it passes.

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — pass.
2. `make lint` — pass.
3. Migration is autogenerate-clean (running `alembic revision --autogenerate` after upgrade produces an empty diff).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00017",
  "completion_status": "complete",
  "files_changed": [
    "orch/db/migrations/versions/{hash}_add_pending_migration_log.py",
    "orch/db/models.py",
    "tests/integration/test_pending_migration_log_migration.py"
  ],
  "tests_passed": true,
  "test_summary": "N passed, 0 failed",
  "blockers": [],
  "notes": "New alembic head is {hash}. Migration lock released."
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00017 --step S01
# ...
uv run iw step-done CR-00017 --step S01 --report ai-dev/active/CR-00017/reports/CR-00017_S01_Database_report.md
```
