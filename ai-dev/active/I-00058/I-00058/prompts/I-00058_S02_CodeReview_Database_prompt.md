# I-00058_S02_CodeReview_Database_prompt

**Work Item**: I-00058 — DocGenerationJob IDs are UUIDs instead of sequential DOC-NNNNN identifiers
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

Allowed exceptions: testcontainers (pytest), read-only introspection, `./ai-core.sh` / `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live DB (port 5433).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00058 --json`
- `ai-dev/active/I-00058/I-00058_Issue_Design.md` — Design document
- `ai-dev/active/I-00058/reports/I-00058_S01_Database_report.md` — S01 implementation report
- All files listed in the S01 report's `files_changed` (models.py + migration file)

## Output Files

- `ai-dev/active/I-00058/reports/I-00058_S02_CodeReview_Database_report.md` — Review report

## Context

You are reviewing the database changes made in S01 by `database-impl` for **I-00058**.

The intent: add a nullable `public_id TEXT` column with a unique index to `doc_generation_jobs`, and generate the corresponding Alembic migration. The `before_insert` event listener is intentionally deferred to S03 (Backend) — do not flag its absence as a finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Report any new violations in changed files as CRITICAL findings.

## Review Checklist

### 1. Model correctness
- Is `public_id` declared as `Mapped[str | None]` (nullable)?
- Is it placed after the `id` column, consistent with `CodeIndexJob`?
- Is the unique index correctly named (`ix_doc_generation_jobs_public_id`)?
- Does the comment describe the DOC-NNNNN format and `id_sequences['DOC']` allocation?

### 2. Migration correctness
- Does `upgrade()` add the column as nullable TEXT with a unique index?
- Does `downgrade()` drop both the index and the column in the correct order?
- Does the migration NOT backfill existing rows?
- Does `alembic history` show this revision chains correctly from the prior head?
- Are there any unrelated schema changes captured by autogenerate? (Flag as HIGH if yes.)

### 3. Scope discipline
- Is the `before_insert` event listener absent from this step? (It belongs in S03.)
- Are no other models or files modified beyond `models.py` and the migration?

### 4. Project conventions
- SQLAlchemy 2.0 `Mapped[]` declarative style used correctly?
- No psycopg2 imports or URL patterns introduced?

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | Breaks migration chain, data loss risk, wrong column type |
| HIGH | Migration captures unrelated changes, column non-nullable when should be nullable |
| MEDIUM (fixable) | Wrong index name, missing comment, ordering inconsistency |
| MEDIUM (suggestion) | Alternative design |
| LOW | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00058",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
