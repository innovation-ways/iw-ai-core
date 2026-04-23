# F-00060_S01_Database_prompt

**Work Item**: F-00060 — Hybrid Code Q&A retrieval
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network mutation command.
Testcontainers via pytest fixtures are allowed.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade | downgrade | stamp` against the live
orchestration DB (port 5433). Write the migration file; the daemon applies
it post-merge. `alembic revision --autogenerate -m "..."` is allowed (writes
a file). Running migrations inside testcontainer fixtures is allowed.

See `docs/IW_AI_Core_Agent_Constraints.md` for the full policy.

---

## Input Files

- `ai-dev/active/F-00060/F-00060_Feature_Design.md` — see *Database Changes*, *Invariants*
- `orch/db/models.py` — existing `CodeIndexJob` class (approx. lines 1193–1266) to mirror
- `orch/db/migrations/versions/` — locate the migration that added `code_index_jobs`; use it as a structural template

## Output Files

- `ai-dev/active/F-00060/reports/F-00060_S01_Database_report.md` (new)
- `orch/db/models.py` (modified — new `DocIndexJob` class)
- `orch/db/migrations/versions/{hash}_add_doc_index_jobs.py` (new)

## Context

F-00060 indexes work-item functional docs into LanceDB via a sibling of the
existing `code_index_jobs` infrastructure. This step adds the DB row.

## Requirements

### 1. `DocIndexJob` ORM class

Add to `orch/db/models.py` adjacent to `CodeIndexJob`. Columns mirror
`code_index_jobs` exactly, with two renames:

- `id` TEXT PRIMARY KEY (UUID-as-TEXT)
- `project_id` TEXT FK → `projects.id`, NOT NULL, `ON DELETE CASCADE`
- `status` TEXT NOT NULL DEFAULT `'queued'`
- `provider` TEXT NOT NULL DEFAULT `'local'`
- `llm_model`, `embed_model`, `index_tier` TEXT NULL
- `items_discovered` INT NOT NULL DEFAULT 0 (was `files_discovered`)
- `items_indexed` INT NOT NULL DEFAULT 0 (was `files_indexed`)
- `chunks_created` INT NOT NULL DEFAULT 0
- `errors` JSONB NOT NULL DEFAULT `[]`
- `triggered_at` TIMESTAMPTZ NOT NULL DEFAULT `NOW()`
- `started_at`, `completed_at` TIMESTAMPTZ NULL
- `error_message` TEXT NULL

SQLAlchemy 2.0 `Mapped[]` style, same column styling (typed, nullable flags,
`server_default=`) as `CodeIndexJob`. Add `back_populates` on `Project` if
the existing `CodeIndexJob` has one.

### 2. Alembic migration

Run `uv run alembic revision --autogenerate -m "add doc_index_jobs"` and
hand-edit to:

- `upgrade()`:
  - `op.create_table("doc_index_jobs", ...)` with all columns above.
  - `op.create_index("idx_doc_index_jobs_project_id", "doc_index_jobs", ["project_id"])`.
  - `op.create_index("idx_doc_index_jobs_status", "doc_index_jobs", ["status"])`.
- `downgrade()`:
  - `op.drop_index("idx_doc_index_jobs_status", "doc_index_jobs")`.
  - `op.drop_index("idx_doc_index_jobs_project_id", "doc_index_jobs")`.
  - `op.drop_table("doc_index_jobs")`.

`down_revision` must chain from the current head (check `alembic history`).
If F-00059's migration is already merged, chain from that one.

### 3. No FTS, no enums

The `status` column is plain TEXT with application-layer validation (same as
`code_index_jobs`). No PG enum type is created. No FTS trigger is needed —
this table is not searched by content.

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`. Match the exact patterns used by
`code_index_jobs` — naming, types, index style, nullability. psycopg v3.
SQLAlchemy 2.0 typed style.

## TDD Requirement

1. **RED**: `tests/integration/test_doc_index_jobs_migration.py` asserting:
   - Table exists after `upgrade`.
   - All columns with expected types and defaults.
   - Both indexes exist.
   - INSERT with only required columns succeeds.
   - `downgrade` drops table + indexes cleanly; `upgrade` then re-creates them.
2. **GREEN**: ORM class + migration.
3. **REFACTOR**: verify symmetry line-by-line with `code_index_jobs` in a
   diff and note any deliberate differences in the step report.

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — pass.
2. `make lint` — pass.
3. `make typecheck` — pass.

## Subagent Result Contract

Standard JSON with `step: "S01"`, `agent: "database-impl"`, `work_item: "F-00060"`.
