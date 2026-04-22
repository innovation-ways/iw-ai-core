# F-00058_S01_Database_prompt

**Work Item**: F-00058 — OSS compliance dashboard view + status pill
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
cause multi-hour outages and data loss (2026-04-22 incident).

Allowed:
  1. Testcontainers spun up by pytest fixtures (they self-destruct via Ryuk).
  2. Read-only introspection: docker ps | inspect | logs.
  3. Invocations through ./ai-core.sh or make targets.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule. If a testcontainer appears
stuck, rely on pytest teardown / Ryuk — never `docker kill` it.

---

## Input Files

- `ai-dev/active/F-00058/F-00058_Feature_Design.md` — Database Changes + Invariants

## Output Files

- `ai-dev/active/F-00058/reports/F-00058_S01_Database_report.md`
- `orch/db/migrations/versions/{hash}_add_project_oss_job.py` (new)
- `orch/db/models.py` (modified — add `ProjectOssJob`)

## Context

F-00057 adds `project.oss_enabled` + `oss_scan`/`oss_finding`/`oss_tool_run` tables. This step adds one more table, `project_oss_job`, which the dashboard uses to track async scan/prepare/publish jobs (distinct from `oss_scan`: a job can fail before any oss_scan row is created).

## Requirements

### 1. Alembic migration

Create `project_oss_job` per design doc's *Database Changes* section:
- BIGSERIAL PK, `project_id` FK (`ON DELETE CASCADE`).
- `kind` enum (`scan`/`prepare`/`publish`/`install`) named `project_oss_job_kind`. `install` tracks Tier-1 tool installation jobs triggered by the dashboard's Install-now button; it wraps `iw oss install` from F-00057. No worktree — install jobs leave `worktree_path` null.
- `status` enum (`queued`/`running`/`complete`/`error`/`cancelled`) named `project_oss_job_status`.
- `scan_id` nullable FK → `oss_scan.id`, `ON DELETE SET NULL`.
- `stdout_tail TEXT` (16KB cap enforced at app layer, not DB).
- Indexes: `(project_id, created_at DESC)`, `(status)`.
- Downgradeable.

### 2. ORM model

`ProjectOssJob` in `orch/db/models.py`:
- SQLAlchemy 2.0 typed style, matches migration.
- `back_populates` to `Project.oss_jobs`.
- Optional relationship to `OssScan` (when `scan_id` set).

### 3. Migration lock coordination

Use `iw migration-lock` before running `alembic revision --autogenerate`; release on completion. Per CLAUDE.md, never run migrations against the live DB during tests.

## Project Conventions

Read CLAUDE.md, `orch/db/models.py`, and recent migrations for patterns.

## TDD Requirement

1. RED: `tests/integration/test_project_oss_job_migration.py` asserting table/column/enum/index presence + downgrade reversibility.
2. GREEN: migration + model.
3. REFACTOR.

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — pass.
2. `make lint` — pass.

## Subagent Result Contract

Standard JSON with `step: "S01"`, agent `database-impl`, `work_item: "F-00058"`.
