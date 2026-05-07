# CR-00036_S02_CodeReview_prompt

**Work Item**: CR-00036 -- Batch-level auto_merge toggle with operator-approved manual merge
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
infrastructure containers are outside your scope.

Allowed exceptions: testcontainers via pytest fixtures, read-only `docker ps`/`inspect`/`logs`, `./ai-core.sh` and `make` targets. If a prohibited command seems necessary, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live DB. Allowed: `alembic revision --autogenerate`, `alembic history|current|show`, testcontainer fixtures. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00036/CR-00036_CR_Design.md`
- `ai-dev/work/CR-00036/reports/CR-00036_S01_Database_report.md`
- All files listed in S01's `files_changed`.

## Output Files

- `ai-dev/work/CR-00036/reports/CR-00036_S02_CodeReview_report.md`

## Context

You are reviewing the database changes for CR-00036. The CR adds a `Batch.auto_merge` boolean and a new `BatchItemStatus.awaiting_merge_approval` enum value, plus an Alembic migration and schema doc updates.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files listed in S01's `files_changed`:

```bash
make lint
make format
```

Any NEW violations on changed files become CRITICAL findings under `category: conventions`. If `make` is unavailable, raise a blocker.

## Review Checklist

### 1. Schema correctness

- `Batch.auto_merge` column: `Boolean`, NOT NULL, `server_default=text("true")`, comment present, placed near `auto_publish` for cohesion.
- New enum member positioned reasonably; `value` string equals `"awaiting_merge_approval"`.
- `awaiting_merge_approval` is **NOT** in `TERMINAL_BATCH_ITEM_STATUSES` (it's transient).
- No drift between Python enum, SQL enum, and migration.

### 2. Migration correctness

- `down_revision` chains correctly off the current head (verify with `alembic history`).
- Enum-add uses `ALTER TYPE … ADD VALUE IF NOT EXISTS` inside an `autocommit_block()`. CRITICAL if it runs inside a transaction.
- Enum-add precedes any code that references the new value.
- `downgrade()` is implemented (drop column + swap-type pattern). Pure NotImplementedError or empty body is a HIGH finding given the CR's rollback plan calls for it.
- The downgrade guard against rows still holding the new enum value is present and raises a clear error.
- Filename matches `cr00036_*.py`.

### 3. Schema doc accuracy

- DDL block in `docs/IW_AI_Core_Database_Schema.md` shows the new column with the same default and NOT-NULL.
- Enum section lists the new value.
- State-machine section adds the new transitions (`executing → awaiting_merge_approval`, `awaiting_merge_approval → completed`).

### 4. Test coverage

- Tests assert default = `True`, round-trip `False`, enum string value, and persistability of a row in the new state.
- Tests use testcontainer (`db_session` fixture or equivalent) — never the live DB on 5433.

### 5. Project conventions

- `Mapped[bool]` style, not bare `bool`.
- `server_default=text("true")`, not `default=True`.
- Comment text is present and informative.

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` and `make test-integration` to confirm no regressions and that the new migration applies cleanly inside the testcontainer fixture.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | Migration won't run, enum mismatch, schema doc divergence on DDL |
| HIGH | Missing downgrade, missing guard, naming/placement violations |
| MEDIUM (fixable) | Missing comment, weak test, minor convention drift |
| MEDIUM (suggestion) | Style improvement |
| LOW | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00036",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings; `fail` otherwise.
