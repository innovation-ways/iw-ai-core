# I-00058_S01_Database_prompt

**Work Item**: I-00058 — DocGenerationJob IDs are UUIDs instead of sequential DOC-NNNNN identifiers
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

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00058 --json`
- `ai-dev/active/I-00058/I-00058_Issue_Design.md` — Design document
- `orch/db/models.py` — ORM models (see `DocGenerationJob` class at line ~1322 and `CodeIndexJob` at line ~1451 for the pattern to follow)

## Output Files

- `orch/db/models.py` — modified to add `public_id` column to `DocGenerationJob`
- `orch/db/migrations/versions/<revision>_add_doc_generation_jobs_public_id.py` — new Alembic migration
- `ai-dev/active/I-00058/reports/I-00058_S01_Database_report.md` — Step report

## Context

You are fixing the database layer for **I-00058: DocGenerationJob IDs are UUIDs instead of sequential DOC-NNNNN identifiers**.

`DocGenerationJob` (in `orch/db/models.py`, class starts at line ~1322) assigns a raw UUID as its `id` primary key and has no human-readable sequential identifier. Every other job type uses a `public_id` column allocated from the `id_sequences` table via a SQLAlchemy `before_insert` event listener. This step adds the `public_id` column to the model and generates the corresponding migration. The event listener that populates `public_id` is added in **S03 (Backend)** — your job here is only the schema column.

## Requirements

### 1. Add `public_id` column to `DocGenerationJob` in `orch/db/models.py`

Follow the exact pattern used by `CodeIndexJob` (lines ~1462–1465 and ~1531):

```python
public_id: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    comment="Human-readable ID (DOC-00001, DOC-00002, ...). Allocated via id_sequences['DOC'].",
)
```

Add a `UniqueConstraint` or `Index` for `public_id` in `__table_args__`:

```python
Index("ix_doc_generation_jobs_public_id", "public_id", unique=True),
```

Place the `public_id` column immediately after the `id` column (line ~1331) for consistency with `CodeIndexJob`.

**Do NOT add the `before_insert` event listener here** — that is S03's responsibility.

### 2. Generate the Alembic migration

Run:

```bash
uv run alembic revision --autogenerate -m "add_doc_generation_jobs_public_id"
```

Verify the generated migration:
- `upgrade()` adds a nullable `public_id TEXT` column and a unique index to `doc_generation_jobs`.
- `downgrade()` drops the index and column.
- The migration does NOT backfill existing rows (existing rows keep `public_id = NULL`).
- Check `alembic history` to confirm the revision chains correctly from the current head.

If autogenerate produces unexpected output, hand-write the migration rather than including unrelated changes.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for all project conventions:

- SQLAlchemy 2.0 `Mapped[]` declarative style
- `psycopg` v3 driver (not psycopg2) — relevant for testcontainer URL in tests
- Migration constraint: WRITE only, never apply to live DB

## TDD Requirement

After adding the column to the model, verify the schema change is correctly captured:

1. Run `uv run alembic history` to confirm the new revision is in the chain.
2. Run `make test-unit` — unit tests should not be affected by a schema-only addition.
3. Do **not** write integration tests in this step — that is S05's job.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. **`make format`** — auto-fix formatting drift
2. **`make typecheck`** — zero errors on touched files
3. **`make lint`** — zero errors

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "I-00058",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<revision>_add_doc_generation_jobs_public_id.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
