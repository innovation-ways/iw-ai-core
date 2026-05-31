# F-00092_S01_Database_prompt

**Work Item**: F-00092 — Tier-1 orchestration DB backups
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

No container/volume state changes. Read-only `docker ps/inspect/logs` only.
Testcontainer fixtures are exempt.

## ⛔ Migrations: agents generate, daemon applies

You WRITE the migration file; the daemon applies it. Generate it with
`make migration-pending MSG="add db_backup_jobs"` (sets `down_revision = "PENDING"`,
resolved at merge — CR-00091). Do NOT call `alembic revision --autogenerate`
directly and do NOT run `alembic upgrade` against the live DB.

## Input Files

- `uv run iw item-status F-00092 --json` — runtime step state.
- `ai-dev/active/F-00092/F-00092_Feature_Design.md` — design (read **Database
  Changes** + **Invariants**).
- `orch/db/models.py` — existing job models to mirror: `DocGenerationJob`,
  `CodeIndexJob`, `ChatSummarizationJob` (status enums, timestamp columns, JSON
  columns, naming).
- `CLAUDE.md` — note the `DaemonEvent.metadata` → `event_metadata` reservation rule
  and ORM conventions.

## Output Files

- `ai-dev/active/F-00092/reports/F-00092_S01_Database_report.md`.

## Context

Add the `DbBackupJob` model + migration to record every backup the engine produces
(scheduled and manual). This is the persistence layer the daemon scheduler (S06),
CLI (S09), and Jobs UI (S08) build on.

## Requirements

### 1. `DbBackupJob` ORM model in `orch/db/models.py`

Mirror the style of existing `*Job` models. Columns (final names at your
discretion, but cover):
- `id` (PK, consistent with other job tables — global id sequence if that's the
  pattern).
- `backup_type` — scheduled | manual (use an enum or constrained text consistent
  with how other models do enums; **remember SQLAlchemy reserves `metadata`** — do
  not name any column `metadata`).
- `label` (nullable text — for `--label`).
- `status` — queued | running | success | failed.
- `path` (text — the backup set location), `bytes` (nullable int).
- `alembic_revision` (text, nullable), `instance_id` (UUID/text, nullable),
  `row_counts` (JSON, nullable — e.g. `{"projects": n, "batches": n, "work_items": n}`).
- `error` (nullable text).
- `created_at`, `started_at` (nullable), `finished_at` (nullable) — timezone-aware,
  matching the project's existing datetime convention.
- Index on (`backup_type`, `status`, `created_at`) to support catch-up + prune
  queries efficiently.

### 2. Migration

Run `make migration-pending MSG="add db_backup_jobs"`. Confirm the generated file
has `down_revision = "PENDING"`, creates the `db_backup_jobs` table and the index,
and that `downgrade()` drops them. Do not hand-edit the revision id.

## Project Conventions

Match `orch/db/models.py` patterns exactly (enum handling, id generation, JSON
columns, `__tablename__`, server defaults). Read `CLAUDE.md` ORM rules.

## TDD Requirement

The behavioural/round-trip tests are authored in S11. For this step, the schema is
validated by the S02 `migration-check` gate (round-trip + drift). Do a quick local
check that the model imports cleanly and `Base.metadata` includes the new table.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` — zero new errors in files you touched.

## Migration Verification (NON-NEGOTIABLE)

Run `make migration-check` (fresh testcontainer: upgrade-from-base, schema ==
`Base.metadata.create_all()`, downgrade→upgrade round-trip). Fix the model or
migration until it is green. Do not report `tests_passed: true` while it is red.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00092",
  "completion_status": "complete",
  "files_changed": ["orch/db/models.py", "orch/db/migrations/versions/<rev>_add_db_backup_jobs.py"],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "make migration-check: round-trip + drift OK",
  "tdd_red_evidence": "n/a — schema step; behavioural tests in S11",
  "blockers": [],
  "notes": "Record final column names + enum approach for downstream steps."
}
```
