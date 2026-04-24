# CR-00021_S02_CodeReview_prompt

**Work Item**: CR-00021 -- Rebase alembic down_revision at merge time
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Testcontainer fixtures only. No `docker compose up/down/stop/kill/rm`. Read-only `docker ps` / `docker inspect` / `docker logs` are fine. `./ai-core.sh` / `make` are fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live DB. The daemon is the only entity allowed to apply migrations. Testcontainer fixtures are the only way to exercise migrations in review. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00021/CR-00021_CR_Design.md` — Design document (Impact Analysis, Data Migration, Rollback Plan)
- `ai-dev/active/CR-00021/reports/CR-00021_S01_Database_report.md` — S01 implementation report (includes migration revision hash)
- `orch/db/models.py` (modified by S01) — `BatchItemStatus` enum, `PendingMigrationLog` class
- `orch/db/migrations/versions/<hash>_cr_00021_rebase_pipeline_phase.py` — the new migration
- `orch/db/migrations/versions/9ef17911f546_cr_00019_add_awaiting_review_discarded_.py` — **style reference** for enum-add migrations
- `docs/IW_AI_Core_Database_Schema.md` (modified by S01)

## Output Files

- `ai-dev/active/CR-00021/reports/CR-00021_S02_CodeReview_report.md` — review report

## Context

Review S01's schema-only work: a new `BatchItemStatus` Python enum member, a new `PendingMigrationLog.old_revision` ORM column, and one Alembic migration that adds the PG enum value, relaxes `ck_pending_migration_log_phase` to 4 values, and adds the column. Documentation is updated to match.

The design document's "Data Migration" section and the CR-00019 precedent are the canonical specifications — cross-check S01 against both.

## Review Checklist

### 1. Migration file structure

- Module docstring names the CR and summarises the 3 deltas?
- Revision identifiers match Alembic autogen output (do not hand-pick)?
- `down_revision` points at a valid main-repo revision, not a fabricated/omitted one?

### 2. Enum addition — PG strictness

- `ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'migration_rebase_failed'` runs inside `with op.get_context().autocommit_block():` — NOT in the implicit migration transaction? (Postgres 12+ does permit `ALTER TYPE ... ADD VALUE` in a transaction — CR-00019 uses the plain-`op.execute` form — but the autocommit block is safer when the new label might be referenced by a subsequent statement in the same migration. Either form is acceptable; flag a CRITICAL only if the new value is USED in this migration without autocommit.)
- `IF NOT EXISTS` present (re-runnability under partial-failure recovery)?
- The surrounding pattern (docstring mentions the enum-label dormant-orphan trade-off; `op.execute` call precedes the column/constraint edits) is consistent with CR-00019's migration.

### 3. CHECK constraint recreation

- Drop + recreate happens as two atomic statements inside the main transaction (NOT in the autocommit block — the autocommit block is only for `ALTER TYPE`)?
- New predicate string exactly `"phase IN ('dry_run', 'apply', 'rollback', 'rebase')"` (single quotes, lowercase)?
- Constraint name `ck_pending_migration_log_phase` preserved?

### 4. Column addition

- `op.add_column("pending_migration_log", sa.Column("old_revision", sa.Text(), nullable=True, comment="..."))` — no server_default (NULL is semantically correct for non-rebase rows)?
- Type is `Text` (matches other revision-string columns), not `String(N)`?
- ORM side (`PendingMigrationLog.old_revision`) is `Mapped[str | None]`, placed near `revision`, matches the migration's column definition (type, nullable, comment)?

### 5. `downgrade()` correctness

- Drops column first (no FK, safe order)?
- Restores 3-value CHECK constraint with exact string `"phase IN ('dry_run', 'apply', 'rollback')"`?
- Does NOT attempt to drop the enum label (would fail)?
- Docstring or inline comment documents the dormant-orphan trade-off?

### 6. Python enum addition

- `BatchItemStatus.migration_rebase_failed = "migration_rebase_failed"` (lowercase value, matches PG)?
- Placed immediately after `migration_rolled_back` for locality?
- No other enum values accidentally reordered or renamed?

### 7. Schema documentation

- `batch_item_status` enum list includes `migration_rebase_failed` with a one-line description?
- `pending_migration_log` section documents `old_revision` column + updated CHECK?
- Tone matches surrounding sections (no heavy re-write of neighbouring content)?

### 8. Project conventions

- No `from __future__ import annotations` added to `orch/db/models.py`?
- Migration imports only `from alembic import op` and `import sqlalchemy as sa` (psycopg-safe)?
- Names follow `ck_*` / `ix_*` / `uq_*` / `fk_*` conventions?
- Migration file passes `make lint` / `make format` / `make typecheck`?

### 9. Round-trip verification (RE-RUN IT)

- Run `make test-integration` yourself: must pass. The `pg_engine` fixture applies every migration to a fresh container.
- If time permits, inspect the upgraded schema via psycopg in a one-off scratch test: confirm enum has 12 values, CHECK predicate shows 4-value list, column exists.

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-integration` — must pass
2. Run `make lint` / `make format` / `make typecheck` — must pass
3. Report test results accurately

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Migration cannot apply (ALTER TYPE in-transaction, missing IF NOT EXISTS causing re-run failure, broken CHECK predicate) | Must fix before merge |
| **HIGH** | Downgrade fails, enum desync between Python and PG, schema doc missing new enum value | Must fix before merge |
| **MEDIUM (fixable)** | Comment missing, column placement inconsistent, style drift from CR-00019 pattern | Should fix |
| **MEDIUM (suggestion)** | Naming nitpick, docstring clarity | Optional |
| **LOW** | Whitespace / ordering preference | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00021",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "migration|enum|check_constraint|column|convention|docs|testing",
      "file": "orch/db/migrations/versions/<hash>_cr_00021_rebase_pipeline_phase.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "integration X passed; upgrade/downgrade round-trip verified",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL + HIGH + MEDIUM (fixable) findings. `fail` otherwise.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM (fixable) only.
