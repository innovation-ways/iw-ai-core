# F-00079_S01_Database_prompt

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
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

Allowed exceptions: testcontainers spun up by pytest fixtures; read-only
introspection (`docker ps`, `docker inspect`, `docker logs`); invoking
`./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade`, `alembic downgrade`, or `alembic stamp`
against the live orchestration DB (port 5433). Your job is to WRITE the
migration FILE only. The daemon will apply it through the merge pipeline
(pre-merge dry-run against a testcontainer, post-merge apply to live DB).

Allowed for agents:
- `uv run alembic revision --autogenerate -m "..."` (writes a file only)
- `uv run alembic history` / `current` / `show` (read-only)
- Running migrations inside testcontainer fixtures

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## Input Files

- **Runtime step state** — `uv run iw item-status F-00079 --json` (canonical)
- `ai-dev/active/F-00079/F-00079_Feature_Design.md` — design document
- `orch/db/models.py:406` — existing `WorkItem` ORM model
- `orch/db/models.py:656` — existing `StepRun` ORM model
- `docs/IW_AI_Core_Database_Schema.md` — schema reference

## Output Files

- New migration file under `orch/db/migrations/versions/<auto>_files_view_diff_columns.py`
- Updated `orch/db/models.py` with two new mapped columns on `WorkItem` and two on `StepRun`, plus one (`merge_commit_sha`) on `WorkItem`
- `ai-dev/active/F-00079/reports/F-00079_S01_Database_report.md`

## Context

You are implementing the database layer for **F-00079: Files view**. The Files tab needs three sources of git diff data: (a) live worktree, (b) lazy `git diff` against the squash commit on `main`, and (c) DB-stored snapshot for archived items. This step adds the columns required for sources (b) and (c) and for per-step drilldown.

Read the design document fully before starting — pay attention to the `Schema additions` section, the `Boundary Behavior` table, and the `Invariants` list (specifically Invariant 6: append-only safety on `step_runs`).

## Requirements

### 1. Add columns to `work_items`

Three new nullable columns on `work_items`:

| Column | Type | Constraint | Comment |
|---|---|---|---|
| `diff_text` | `TEXT` | nullable | Raw unified diff of the squash commit captured at merge time. PostgreSQL TOAST handles compression. |
| `diff_summary` | `JSONB` | nullable | Parsed file metadata: list of objects with keys `path`, `status` (one of `A`/`M`/`D`/`R`), `added` (int), `removed` (int), `is_generated` (bool), `is_binary` (bool), `old_path` (str or null). |
| `merge_commit_sha` | `TEXT` | nullable | SHA of the squash commit on `main`. Allows lazy `git diff <sha>^..<sha>` for completed-not-archived items. |

All three columns are NULL on existing rows; no server defaults are needed; no NOT NULL constraints; no indexes that would scan existing rows.

### 2. Add columns to `step_runs`

Two new nullable columns on `step_runs`:

| Column | Type | Constraint | Comment |
|---|---|---|---|
| `diff_text` | `TEXT` | nullable | Raw unified diff captured at `iw step-done` from the worktree. |
| `diff_summary` | `JSONB` | nullable | Parsed file metadata, same shape as `work_items.diff_summary`. |

`step_runs` is append-only at the row level (existing rows are never replaced) but field updates within a row's lifecycle are allowed — see `orch/cli/step_commands.py:380-389` where `status`, `completed_at`, `duration_secs`, `report_file`, `log_content` are all written during the same `step-done` transaction that finalises the row. The new diff columns will follow the same pattern in S03; this step only adds them.

### 3. Update ORM models

In `orch/db/models.py`:

- `WorkItem` (around line 406): add three `Mapped[str | None]` / `Mapped[Any | None]` columns matching the migration. Use the existing column-comment style for documentation.
- `StepRun` (around line 656): add two `Mapped[...]` columns matching the migration.

Match existing naming, typing, and JSONB column patterns elsewhere in the file (e.g., `WorkItem.config` and `WorkItem.impacted_paths` for JSONB precedent).

### 4. Generate the migration via autogenerate

Run:

```bash
uv run alembic revision --autogenerate -m "add files view diff columns to work_items and step_runs"
```

Review the generated file for correctness:
- It MUST contain only `op.add_column` calls (5 total: 3 on `work_items`, 2 on `step_runs`).
- It MUST NOT contain unrelated diffs caused by autogenerate misreading other columns. Edit the file to remove any spurious operations.
- The `downgrade()` function MUST drop the columns in reverse order.

Verify the migration applies cleanly inside a testcontainer (the test fixtures will exercise this in S09; you should at minimum run `make test-unit` to confirm import correctness).

### 5. Schema doc update (if applicable)

`docs/IW_AI_Core_Database_Schema.md` documents the schema. If the file lists `work_items` and `step_runs` columns explicitly, add the new columns there. If it refers to the ORM file as the source of truth, no doc update is needed. Use your judgement — do not introduce drift.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`:
- ORM is SQLAlchemy 2.0 sync with `Mapped[]` declarative style.
- Driver is `psycopg` v3 (NOT psycopg2). Migrations use the same.
- `DaemonEvent.metadata` is named `event_metadata` in Python because SQLAlchemy reserves `metadata` — irrelevant here but keep an eye out for similar gotchas.
- Composite PKs `(project_id, id)` for `work_items`; `step_runs` PK is `id` (autoincrement) with FK to `workflow_steps.id` and `UniqueConstraint("step_id", "run_number")`.
- Append-only convention applies to row creation, not to in-flight field updates during the row's finalisation transaction.

Match existing code in the same file. When unsure, mirror an existing JSONB column declaration (e.g., `WorkItem.config`).

## TDD Requirement

For schema changes, the meaningful test is "does the migration apply and the model load cleanly?" — exercised by the existing testcontainer fixtures in S09. You do not need to write a dedicated unit test for column existence; the integration tests in S09 will surface any breakage. Confirm `make test-unit` passes locally to catch import errors.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift on touched files.
2. `make typecheck` — must report zero errors involving `orch/db/models.py` or the new migration file.
3. `make lint` — must report zero errors.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` must pass with zero failures.
2. The new migration file must be importable (alembic loads it on `alembic history`).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00079",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<auto>_files_view_diff_columns.py"
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
