# CR-00028_S02_CodeReview_Database_prompt

**Work Item**: CR-00028 -- Don't cascade merge-time failures to dependent items
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY Docker mutating command. Allowed: testcontainers via pytest, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00028 --json`
- `ai-dev/active/CR-00028/CR-00028_CR_Design.md` — design document
- `ai-dev/active/CR-00028/reports/CR-00028_S01_Database_report.md` — implementation report
- All files in S01's `files_changed`

## Output Files

- `ai-dev/active/CR-00028/reports/CR-00028_S02_CodeReview_Database_report.md`

## Context

You are reviewing the database layer for **CR-00028**. The change adds a single enum value `merge_failed` to `batch_item_status`. Read the design doc first.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on files in S01's `files_changed`:

```bash
make lint
make format
```

NEW violations in changed files = CRITICAL findings (`category: conventions`).

## Review Checklist

### 1. Architecture Compliance

- Is `merge_failed` placed correctly in the `BatchItemStatus` enum, grouped near other merge-pipeline statuses (`migration_invalid`, `migration_rebase_failed`)?
- Is `merge_failed` added to `TERMINAL_BATCH_ITEM_STATUSES`? It must be — this CR splits "terminal" from "blocking-terminal", but the enum-level "terminal" set should still include `merge_failed` (the merge queue treats it as terminal-this-attempt; only the *cascade* gate is non-blocking, and that lives in S03).

### 2. Migration Correctness

- Does `upgrade()` use `ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'merge_failed'` (not raw `ADD VALUE` without idempotency, and not Python-side enum recreation)?
- Is the `downgrade()` a documented no-op with the "PostgreSQL does not natively support removing values from an enum type" comment?
- Are `revision` / `down_revision` chained correctly? Run `uv run alembic history` to verify the new revision lands on the current head.
- Does the migration filename follow the project pattern (`<rev>_cr00028_add_merge_failed.py` or similar)?

### 3. Project Conventions

- SQLAlchemy 2.0 `Mapped[]` style preserved
- Enum values lowercase
- No `metadata` collisions (DaemonEvent gotcha)

### 4. Forward-Safety

- Will the testcontainer dry-run pass? Run a quick mental check: is the SQL syntactically valid for PostgreSQL 14+? (The project uses port 5433 production DB — check `docs/IW_AI_Core_Database_Schema.md` for version.)

### 5. Testing

- The S01 prompt deferred tests to S07. Check `make test-unit` still passes (no test imports break).

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

Must pass. Report results.

## Severity Levels

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00028",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict`: `pass` if 0 CRITICAL + 0 HIGH + 0 MEDIUM (fixable). Else `fail`.
`mandatory_fix_count` = CRITICAL + HIGH + MEDIUM (fixable).
