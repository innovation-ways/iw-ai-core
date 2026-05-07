# CR-00036_S01_Database_prompt

**Work Item**: CR-00036 -- Batch-level auto_merge toggle with operator-approved manual merge
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

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00036/CR-00036_CR_Design.md` — design document (sections "Current Behavior", "Desired Behavior", "Database Changes", and AC1, AC5, AC9, AC10).
- `orch/db/models.py:936-995` (`Batch` model), `:144-173` (`BatchItemStatus` enum + `TERMINAL_BATCH_ITEM_STATUSES`).
- `orch/db/migrations/versions/` — pattern for recent migrations.

## Output Files

- `ai-dev/work/CR-00036/reports/CR-00036_S01_Database_report.md`

## Context

You are implementing the database layer for **CR-00036 — Batch-level auto_merge toggle with operator-approved manual merge**. The CR adds a per-batch `auto_merge` flag and a new transient batch-item state used as a gate in front of the merge queue.

Read the design document first. Then read `CLAUDE.md` and `orch/CLAUDE.md` for ORM conventions.

## Requirements

### 1. Add `auto_merge` column to the `Batch` model

In `orch/db/models.py` after the `auto_publish` column on `Batch` (currently around line 953), add:

```python
auto_merge: Mapped[bool] = mapped_column(
    Boolean,
    nullable=False,
    server_default=text("true"),
    comment="Whether to auto-merge each item to main on success; false → operator must approve each merge",
)
```

Match the style of the surrounding columns (Mapped annotation, server_default text, trailing comma, comment).

### 2. Add `awaiting_merge_approval` to `BatchItemStatus`

In `orch/db/models.py:144`, add `awaiting_merge_approval = "awaiting_merge_approval"` as a new enum member. Position it between `completed` and `merging` so it reads as the natural place where a successful item parks before being released to the merge queue.

Do NOT add this state to `TERMINAL_BATCH_ITEM_STATUSES` — it is **transient**.

### 3. Generate the Alembic migration

Generate a new migration file with `uv run alembic revision --autogenerate -m "cr00036 auto_merge gate"`. The autogenerate output may need hand-editing — at minimum:

- The new enum value MUST be added via `op.execute("ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'awaiting_merge_approval'")` inside `op.get_context().autocommit_block()` (older Postgres versions reject `ADD VALUE` inside a transaction). Place the enum-add BEFORE the column-add so a single upgrade step can run cleanly.
- The column-add is straightforward: `op.add_column('batches', sa.Column('auto_merge', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='...'))`.
- `downgrade()` MUST drop the column AND remove the enum value via the swap-type pattern (create a new enum without the value, alter the column, drop the old enum, rename). Document in the docstring: "Downgrade requires no rows currently hold the new enum value; UPDATE batch_items SET status='completed' WHERE status='awaiting_merge_approval' before downgrading." Add a runtime guard in `downgrade()` that checks for any such rows and raises a clear error if any exist.
- Filename: `cr00036_auto_merge_gate.py` (lowercase, snake_case, matches recent CR migration naming convention).
- `down_revision` must point at the current head — verify with `uv run alembic heads`.

### 4. Update `docs/IW_AI_Core_Database_Schema.md`

In the `batches` DDL block (currently around line 310), add the new column after `auto_publish`:

```sql
auto_merge      BOOLEAN NOT NULL DEFAULT true,
```

Add a corresponding `COMMENT ON COLUMN batches.auto_merge IS '...'` after the `auto_publish` comment.

In the `batch_item_status` enum section, add `awaiting_merge_approval` to the list of values with a one-line note that it is a transient gate state set when `batch.auto_merge=false` and the item finishes its workflow steps successfully.

In the state-machine section that lists transitions, add the row:
- `executing` → `awaiting_merge_approval`: workflow steps complete, batch.auto_merge=false, awaiting operator approval
- `awaiting_merge_approval` → `completed`: operator approves merge via dashboard or `iw item approve-merge`

(Existing `executing → completed` row stays for the `auto_merge=true` path.)

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md`:

- SQLAlchemy 2.0 declarative `Mapped[]` style.
- psycopg v3 driver.
- All ORM models scoped by `project_id` for multi-project isolation (composite PKs).
- The schema doc is hand-authored — keep formatting consistent.

## TDD Requirement

Follow TDD. Before editing the model, add an integration test in `tests/integration/test_models.py` (or a new sibling file) that:

1. Asserts `Batch.auto_merge` defaults to `True` when not specified.
2. Asserts `Batch.auto_merge` round-trips `False`.
3. Asserts `BatchItemStatus.awaiting_merge_approval.value == "awaiting_merge_approval"`.
4. Asserts a `BatchItem` row can be persisted with `status=BatchItemStatus.awaiting_merge_approval` (column accepts the new enum value end-to-end).

Run the test once to see it fail (RED) before writing the model change. Then make it pass (GREEN). Refactor only if necessary.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run these in order and fix issues:

1. **`make format`**
2. **`make typecheck`** — must show zero errors involving files you touched.
3. **`make lint`**

If a tool is unavailable, raise a blocker.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit`
2. `make test-integration` — testcontainer-backed; the migration MUST run cleanly during fixture setup.
3. Do NOT report `tests_passed: true` unless ALL pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00036",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/cr00036_auto_merge_gate.py",
    "docs/IW_AI_Core_Database_Schema.md",
    "tests/integration/test_models.py"
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
