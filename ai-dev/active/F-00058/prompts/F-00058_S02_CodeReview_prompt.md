# F-00058_S02_CodeReview_prompt

**Work Item**: F-00058
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

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

- `ai-dev/active/F-00058/F-00058_Feature_Design.md`
- `ai-dev/active/F-00058/reports/F-00058_S01_Database_report.md`
- Files listed in S01 report

## Output Files

- `ai-dev/active/F-00058/reports/F-00058_S02_CodeReview_report.md`

## Review Checklist

### 1. Architecture Compliance
- `project_oss_job` schema matches the design's *Database Changes* section exactly.
- `scan_id` uses `ON DELETE SET NULL` (not CASCADE — jobs persist even after scans are purged).
- `project_id` uses `ON DELETE CASCADE`.

### 2. Code Quality
- Enum names match PG enum type names.
- `project_oss_job_kind` includes all four values: `scan`, `prepare`, `publish`, `install`.
- Monotonic status progression is documented (even if not enforced at DB level).
- `stdout_tail` column type is TEXT (not TEXT[], not JSON).

### 3. Conventions
- SQLAlchemy 2.0 typed syntax.
- Matches `orch/db/models.py` style for neighboring models.

### 4. Testing
- Migration test in `tests/integration/test_project_oss_job_migration.py` covers table + enums + indexes + downgrade.
- Testcontainer used per CLAUDE.md (no live DB).
- FTS trigger installed after create_all().

## Test Verification (NON-NEGOTIABLE)

`make test-integration` + `make lint` pass.

## Review Result Contract

Standard JSON. `verdict: pass` only when zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
