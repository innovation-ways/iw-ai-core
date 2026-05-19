# F-00086_S01_Database_prompt

**Work Item**: F-00086 -- Multi-tab AI Assistant on OpenCode
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

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status F-00086 --json`.
- `ai-dev/active/F-00086/F-00086_Feature_Design.md` — design document (read §Scope and §Database Changes in full)

## Output Files

- `orch/db/migrations/versions/<rev>_f_00086_chat_tabs.py` — Alembic revision creating `chat_tabs`
- `orch/db/models.py` — new `ChatTab` ORM model
- `ai-dev/active/F-00086/reports/F-00086_S01_Database_report.md` — Step report

## Context

You are creating the `chat_tabs` table that backs the multi-tab AI Assistant. Each row represents one user-facing chat tab bound to one OpenCode session.

Read the design document first; pay special attention to the **Boundary Behavior** rows that map onto schema decisions (PK type, allowlist enforcement strategy, soft-delete shape, FK cascade behaviour).

## Requirements

### 1. Generate the Alembic revision

Use `alembic revision --autogenerate -m "f_00086_chat_tabs"` to write a new file under `orch/db/migrations/versions/`. The autogen output will be a starting point — hand-tune the body to the spec below.

**Pattern-check first** (before writing): grep `orch/db/migrations/versions/` for prior uses of:
- `gen_random_uuid()` server defaults — if present and pgcrypto is enabled elsewhere, follow the same pattern; if not, use Python-side `uuid.uuid4()` as a `default=` instead.
- `CREATE EXTENSION IF NOT EXISTS pgcrypto` — if present, you may add it to your `upgrade()`.
- Two recent reference migrations: `ff23f562353b_f_00081_agent_runtime_options.py` (table create + indexes + seeds) and `fb7e5859d479_add_fix_summary_to_fix_cycles.py` (column add). Match their style.

### 2. Schema

Create table `chat_tabs` with columns:

| Column | Type | Constraint |
|--------|------|------------|
| `id` | UUID | PK; server default `gen_random_uuid()` if pgcrypto pattern exists, else `default=uuid.uuid4` on the ORM side |
| `title` | TEXT | NOT NULL; default `'New chat'` |
| `runtime` | TEXT | NOT NULL; default `'opencode'`. **No CHECK constraint** — allowlist enforced in `orch/chat/tab_service.py` (matches CR-00062 pattern for `cli_tool`). Column comment: `"Chat runtime: 'opencode' today; 'pi' added by F-B"` |
| `model` | TEXT | NOT NULL |
| `project_id` | TEXT | NOT NULL; FK to `projects.id` ON DELETE CASCADE |
| `opencode_session_id` | TEXT | NULL (populated after first OpenCode session create) |
| `status` | TEXT | NOT NULL; default `'active'`. No CHECK constraint — allowlist `{'active','closed'}` enforced in `tab_service.py`. Column comment: `"Tab status: 'active' or 'closed' (soft-delete)"` |
| `created_at` | TIMESTAMPTZ | NOT NULL; default `now()` |
| `updated_at` | TIMESTAMPTZ | NOT NULL; default `now()` |
| `last_active_at` | TIMESTAMPTZ | NOT NULL; default `now()` |
| `closed_at` | TIMESTAMPTZ | NULL |

Indexes (with explicit names):
- `ix_chat_tabs_status_last_active` on `(status, last_active_at DESC)`
- `ix_chat_tabs_project_status` on `(project_id, status)`

### 3. Race protector for concurrent bootstrap

Add a **partial unique index** as the race-safety mechanism for the `bootstrap_default_tab` helper under concurrent first-load (see design Boundary row "Bootstrap called twice concurrently"):

- `uq_chat_tabs_default_per_project` UNIQUE on `(project_id)` WHERE `title = 'Default' AND status = 'active'`

This index protects ONLY the race window of concurrent first-load: when two requests both see "zero `chat_tabs` rows for project_id" and both try to INSERT a `Default` tab, one wins via the partial unique constraint and the other catches `IntegrityError` and re-fetches the winner's row. The application-layer "no rows for project" check (in `bootstrap_default_tab`) is the actual gate that prevents bootstrap from firing after a user has closed all their tabs — the index does NOT enforce that gate.

Use `op.execute("CREATE UNIQUE INDEX uq_chat_tabs_default_per_project ON chat_tabs (project_id) WHERE title = 'Default' AND status = 'active'")` since Alembic's `create_index(unique=True, postgresql_where=...)` may or may not match exactly — match whichever pattern is already used in `orch/db/migrations/versions/`.

### 4. `downgrade()` body

Drop in reverse order:
1. Drop `uq_chat_tabs_default_per_project`
2. Drop `ix_chat_tabs_project_status`
3. Drop `ix_chat_tabs_status_last_active`
4. Drop table `chat_tabs`

### 5. ORM model

Add a `ChatTab` class to `orch/db/models.py` mirroring the table. Use SQLAlchemy 2.0 `Mapped[...]` style (match existing models). Place the class near other dashboard-feature tables (search for `class Project(` to find the logical block).

If you use a Python-side UUID default (no `gen_random_uuid()`), declare `id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`.

### 6. RUN `make migration-check` before reporting completion

This is NON-NEGOTIABLE per the template's Migration Verification section. The gate spins a fresh testcontainer, runs `alembic upgrade head` from base, asserts `Base.metadata.create_all()` parity, and round-trips `downgrade base → upgrade head`. If it fails (drift, broken downgrade, missing extension, etc.), fix the migration or the model until both halves agree.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for project conventions (SQLAlchemy 2.0 sync, psycopg v3, Alembic 1.13+, `DaemonEvent.event_metadata` rename precedent for reserved `metadata`). Match the column-comment style in existing models (`comment="..."` on `mapped_column`).

## TDD Requirement

Database steps that add ORM models typically pair with `tests-impl` (S08) for behavioural test coverage. For this step, the targeted RED evidence is:

- Capture the `make migration-check` run **before** the migration file is in its final shape — it should fail (no revision yet, or schema parity mismatch). Then after the migration is written, re-run and capture the GREEN output.
- For the ORM model alone, `tdd_red_evidence` may be `"n/a — schema/migration step; behavioural tests added in S08"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — auto-fix formatting drift
2. `make typecheck` — must report zero errors involving the files you touched
3. `make lint` — must report zero errors
4. `make migration-check` — MUST be green

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/migrations/versions/<rev>_f_00086_chat_tabs.py",
    "orch/db/models.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "migration-check: upgrade head + create_all parity + downgrade round-trip all green",
  "tdd_red_evidence": "n/a — schema/migration step; behavioural tests added in S08",
  "blockers": [],
  "notes": ""
}
```
