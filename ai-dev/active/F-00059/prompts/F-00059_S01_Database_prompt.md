# F-00059_S01_Database_prompt

**Work Item**: F-00059 — Functional design documents for work items
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker container/volume/network mutation command
(`docker kill | stop | rm | restart | compose up | compose down | volume rm
| system prune | container prune | image prune`). The orchestration DB,
daemon, and dashboard containers are outside your scope.

Allowed: testcontainers spun up by pytest fixtures (self-destruct via Ryuk),
read-only introspection (`docker ps | inspect | logs`), invocations through
`./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker.

---

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade | downgrade | stamp` against the live
orchestration DB (port 5433). Your job is to WRITE the migration file.
The daemon applies it post-merge via the 3-phase pipeline (dry-run on
testcontainer → apply → auto-rollback on failure). See
`docs/IW_AI_Core_Agent_Constraints.md` (R2).

Allowed for agents:
- `alembic revision --autogenerate -m "..."` (writes a file; may read live schema, which is a read)
- `alembic history | current | show` (read-only)
- Migration applied inside testcontainer fixtures (test-path only)

---

## Input Files

- `ai-dev/active/F-00059/F-00059_Feature_Design.md` — see *Database Changes*, *Invariants*, and *Notes / Trigger naming*
- `orch/db/models.py` — existing `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` patterns to mirror
- `tests/integration/conftest.py` — existing FTS install block

## Output Files

- `ai-dev/active/F-00059/reports/F-00059_S01_Database_report.md` (new)
- `orch/db/models.py` (modified — new columns + new FTS constants)
- `orch/db/migrations/versions/{hash}_add_functional_doc_columns.py` (new)
- `tests/integration/conftest.py` (modified — install new FTS trigger)

## Context

F-00059 adds a second, human-facing "functional design document" per work item.
This step wires the DB layer: three new columns on `work_items` plus a trigger-
maintained FTS column that mirrors the existing `design_doc_search` pattern
exactly. No other layers yet — backend, template, and frontend work happen in
S02, S03, S04 respectively.

## Requirements

### 1. ORM model changes — `orch/db/models.py`

Add three columns to `WorkItem`, immediately after the existing `design_doc_*`
trio. Use the same types, nullability, and `comment=` style as the existing
columns:

- `functional_doc_path: Mapped[str | None]` — `Text`, nullable.
- `functional_doc_content: Mapped[str | None]` — `Text`, nullable.
- `functional_doc_search: Mapped[str | None]` — `TSVECTOR`, nullable.

Add two new module-level constants alongside `FTS_FUNCTION_SQL` and
`FTS_TRIGGER_SQL`:

- `FUNCTIONAL_DOC_FTS_FUNCTION_SQL` — defines PL/pgSQL function
  `work_items_functional_doc_search_update()` that sets
  `NEW.functional_doc_search = to_tsvector('english', COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.functional_doc_content, ''))`.
- `FUNCTIONAL_DOC_FTS_TRIGGER_SQL` — `CREATE TRIGGER work_items_functional_doc_search_trg BEFORE INSERT OR UPDATE OF title, functional_doc_content ON work_items FOR EACH ROW EXECUTE FUNCTION work_items_functional_doc_search_update();`.

Mirror the existing constants' string style. Do NOT rename or modify the
existing `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` — they must remain byte-for-
byte unchanged (Invariant 7).

### 2. Alembic migration

Run `uv run alembic revision --autogenerate -m "add functional_doc columns to work_items"`
and then hand-edit the resulting file to:

- `upgrade()`:
  1. `op.add_column("work_items", sa.Column("functional_doc_path", sa.Text(), nullable=True, comment="..."))`
  2. Same for `functional_doc_content`.
  3. `op.add_column("work_items", sa.Column("functional_doc_search", postgresql.TSVECTOR(), nullable=True))`.
  4. `op.execute(text(FUNCTIONAL_DOC_FTS_FUNCTION_SQL))` (import from `orch.db.models`).
  5. `op.execute(text(FUNCTIONAL_DOC_FTS_TRIGGER_SQL))`.
  6. `op.create_index("idx_work_items_functional_doc_search", "work_items", ["functional_doc_search"], postgresql_using="gin")`.
- `downgrade()`: drop index → drop trigger → drop trigger function → drop columns, in that exact order. Use plain `DROP TRIGGER IF EXISTS` / `DROP FUNCTION IF EXISTS` raw SQL for the trigger and function.

`down_revision` must point at the latest existing migration (`fb7e5859d479` or whatever is current — check `alembic history`).

Autogenerate may omit the trigger and function (it doesn't track PL/pgSQL).
You MUST add those `op.execute()` calls by hand. Same for the index — add it
explicitly if autogenerate omits it.

### 3. Testcontainer FTS install — `tests/integration/conftest.py`

The existing fixture installs `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` (and the
`PROJECT_DOCS_*` pair) after `Base.metadata.create_all()`. Add the new pair
immediately after: import `FUNCTIONAL_DOC_FTS_FUNCTION_SQL` and
`FUNCTIONAL_DOC_FTS_TRIGGER_SQL` from `orch.db.models` and execute them in
the same `conn.execute(text(...))` sequence. Commit once at the end, as
today.

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md`. Match the existing
`design_doc_search` pattern exactly — naming, column order, index style.
SQLAlchemy 2.0 typed style (`Mapped[]`). psycopg v3 (not psycopg2). Never
connect tests to the live DB.

## TDD Requirement

1. **RED**: Create `tests/integration/test_work_items_functional_doc_fts.py` asserting:
   - Insert a WorkItem with `title="Hello"` and `functional_doc_content="World"` → `functional_doc_search` contains lexemes `hello` and `world`.
   - Update only `functional_doc_content` → search vector re-generates.
   - Update only `title` → search vector re-generates.
   - `SELECT id FROM work_items WHERE functional_doc_search @@ to_tsquery('english', 'world')` returns the row.
   - The independence invariant: insert WorkItem with `design_doc_content="foo"` and no `functional_doc_content` → `design_doc_search` contains `foo`, `functional_doc_search` contains only title lexemes.
2. **GREEN**: implement columns, constants, migration, conftest update.
3. **REFACTOR**: verify downgrade + upgrade round-trip in a testcontainer.

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — pass (includes the new file).
2. `make lint` — pass.
3. `make type-check` — pass.

Do NOT report `tests_passed: true` unless all three commands exit 0.

## Subagent Result Contract

Standard JSON with `step: "S01"`, `agent: "database-impl"`, `work_item: "F-00059"`. Include the migration filename in `files_changed`.
