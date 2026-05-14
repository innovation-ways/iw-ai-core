# CR-00053_S01_Database_prompt

**Work Item**: CR-00053 -- Idempotent `iw next-id` via `--idempotency-key` flag
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived infrastructure containers are outside your scope. Allowed exceptions: testcontainers spun up by pytest fixtures; read-only introspection (`docker ps`, `docker inspect`, `docker logs`); `./ai-core.sh` and `make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade head`, `alembic upgrade <rev>`, `alembic downgrade <anything>`, or `alembic stamp <anything>` against the live orchestration DB (port 5433). Your job here is to **WRITE the migration FILE**. The daemon applies it as part of the merge pipeline. Allowed: `alembic revision --autogenerate -m "..."` (writes a file only), `alembic history / current / show` (read-only), and migrations inside testcontainer fixtures. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00053/CR-00053_CR_Design.md` -- Design document (Sections "Database Changes", "Desired Behavior", and "Acceptance Criteria")
- `orch/db/models.py` -- ORM models (the `IdSequence` class at line 431 is the existing analog; add the new model nearby for locality)
- `orch/CLAUDE.md` -- migration conventions (psycopg v3, SQLAlchemy 2.0 `Mapped[]` style)

## Output Files

- `ai-dev/work/CR-00053/reports/CR-00053_S01_Database_report.md` -- Step report
- `orch/db/models.py` -- with the new `IdAllocation` class added
- `orch/db/migrations/versions/<rev>_add_id_allocations_table.py` -- the new Alembic revision

## Context

You are implementing the database half of **CR-00053**. Add a small audit table that lets `iw next-id` be idempotent when callers pass a key.

Read the design document first to understand the full scope and your step's deliverables. Then read `CLAUDE.md` and `orch/CLAUDE.md` for project-specific patterns and conventions.

## Requirements

### 1. Add the `IdAllocation` ORM model

Add a new SQLAlchemy 2.0 declarative class to `orch/db/models.py` immediately below the existing `IdSequence` class (line 431). Schema:

| Column | Type | Constraints |
|--------|------|-------------|
| `prefix` | `Text` | `nullable=False`, part of composite PK |
| `number` | `Integer` | `nullable=False`, part of composite PK |
| `idempotency_key` | `Text` | `nullable=True` |
| `project_id` | `Text` | `nullable=True` |
| `created_at` | `TIMESTAMPTZ` | `nullable=False`, `server_default=text("now()")` |

Table comment: `"Audit log of keyed ID allocations for idempotent iw next-id (CR-00053)"`. Composite PK on `(prefix, number)`. Partial unique index on `(prefix, idempotency_key) WHERE idempotency_key IS NOT NULL`, named `idx_id_allocations_key`.

For SQLAlchemy 2.0 `Mapped[]` declarative style, the partial unique index is expressed via `Index("idx_id_allocations_key", "prefix", "idempotency_key", unique=True, postgresql_where=text("idempotency_key IS NOT NULL"))` declared in `__table_args__`.

### 2. Generate the Alembic migration

Run:

```bash
uv run alembic revision --autogenerate -m "Add id_allocations table for idempotent next-id"
```

This writes a file under `orch/db/migrations/versions/`. **Inspect the generated file before reporting**. Autogenerate usually misses the `postgresql_where` clause on partial indexes — if so, hand-edit the migration's `op.create_index(...)` call to include `postgresql_where=sa.text("idempotency_key IS NOT NULL")`. The `downgrade()` body must drop the index first, then the table.

Commit the migration file in this same step (the rule about uncommitted migrations and worktree DBs in `CLAUDE.md` applies — the daemon will fail to launch worktrees if this file is left uncommitted).

### 3. Run `make migration-check` before reporting completion

Per the Migration Verification section below, run `make migration-check` and confirm it exits 0. Capture the output in your report. Do **not** report `tests_passed: true` while this is red.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for:
- SQLAlchemy 2.0 `Mapped[]` declarative style — match `IdSequence` exactly
- psycopg v3 driver (NOT psycopg2) — no driver-specific code anywhere
- Migration generation via `uv run alembic revision --autogenerate -m "..."`
- Table comments via `__table_args__ = ({"comment": "..."},)`

Match the existing `IdSequence` class shape exactly for `Mapped[]` type annotations, `mapped_column` defaults, and `__table_args__` style.

## TDD Requirement

This is a Database step adding schema only — no business logic. **RED phase is satisfied by `make migration-check`**: it fails before the model and migration exist; passes after both are correct. Capture the failing → passing transition in your report's `tdd_red_evidence` field as: `"make migration-check — failed before model+migration added; passed after"`.

Unit/integration tests for the *behavior* of keyed allocation are written in S03 (TDD-RED there) and S04 (integration). Do NOT write them here.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. **`make format`** — auto-fixes formatting drift on `orch/db/models.py` and the new migration.
2. **`make typecheck`** — must report zero errors involving the files you touched.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker.

## Migration Verification (NON-NEGOTIABLE for Database steps)

You MUST run **`make migration-check`** before reporting completion. This spins a fresh testcontainer, runs `alembic upgrade head` from base, asserts schema parity vs `Base.metadata.create_all()`, and round-trips through `downgrade base → upgrade head`. The partial unique index is the most likely autogenerate gap — verify the round-trip explicitly.

## Test Verification

Do NOT run `make test-unit` or `make test-integration` — those are S13 and S14 QV gates. This step's verification is `make migration-check` only.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00053",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<rev>_add_id_allocations_table.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "make migration-check: round-trip + drift OK",
  "tdd_red_evidence": "make migration-check — failed before model+migration added; passed after",
  "blockers": [],
  "notes": ""
}
```
