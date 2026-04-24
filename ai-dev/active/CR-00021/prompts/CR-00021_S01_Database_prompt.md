# CR-00021_S01_Database_prompt

**Work Item**: CR-00021 -- Rebase alembic down_revision at merge time
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker / docker compose command. Testcontainers spun up by pytest fixtures are the ONLY allowed docker usage. Read-only `docker ps` / `docker inspect` / `docker logs` are fine. `./ai-core.sh` and `make` targets are fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

WRITE the migration file. Do NOT run `alembic upgrade/downgrade/stamp` against the live DB. `alembic revision --autogenerate -m "..."` is allowed (file-only). `alembic history / current / show` are allowed (read-only). The daemon applies migrations post-merge. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00021/CR-00021_CR_Design.md` — Design document (read fully, especially "Impact Analysis" and "Data Migration")
- `orch/db/models.py` — existing ORM models; current `BatchItemStatus` enum + `PendingMigrationLog` class (sync SQLAlchemy 2.0 `Mapped[]` style, no `from __future__ import annotations`)
- `orch/db/migrations/versions/9ef17911f546_cr_00019_add_awaiting_review_discarded_.py` — **style reference** for adding a PG enum value via `ALTER TYPE ... ADD VALUE` outside a transaction
- `docs/IW_AI_Core_Database_Schema.md` — update the `batch_item_status` enum list + `pending_migration_log` section

## Output Files

- `orch/db/models.py` (modified) — add `BatchItemStatus.migration_rebase_failed`, add `PendingMigrationLog.old_revision` Mapped column
- `orch/db/migrations/versions/<autogen_hash>_cr_00021_rebase_pipeline_phase.py` (new) — Alembic migration
- `docs/IW_AI_Core_Database_Schema.md` (modified) — reflect the new enum value, CHECK relax, and new column
- `ai-dev/active/CR-00021/reports/CR-00021_S01_Database_report.md` — step report

## Context

This step adds the schema that supports the new `run_pre_merge_rebase` daemon phase (S03/S05). After this step lands, the PG enum + CHECK constraint + column are in place so the module can write `PendingMigrationLog(phase='rebase', old_revision=<prev>)` rows and the merge queue can set `batch_item.status='migration_rebase_failed'`. No daemon code changes here — schema only.

Read the design's "Data Migration" section in full before starting. The CR-00019 migration is the canonical reference for the `ALTER TYPE ... ADD VALUE` pattern.

## Requirements

### 1. Python enum — `BatchItemStatus.migration_rebase_failed`

Add the member to `orch/db/models.py` immediately after `migration_rolled_back = "migration_rolled_back"`:

```python
class BatchItemStatus(enum.Enum):
    # ... existing members ...
    migration_invalid = "migration_invalid"
    migration_rolled_back = "migration_rolled_back"
    migration_rebase_failed = "migration_rebase_failed"  # NEW — CR-00021
```

### 2. ORM column — `PendingMigrationLog.old_revision`

Add to the `PendingMigrationLog` class in `orch/db/models.py`:

```python
old_revision: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    comment="Previous down_revision string before the rebase phase rewrote it (phase='rebase' only)",
)
```

Place the column near `revision` for locality. Do not add a server_default — `NULL` is the correct representation for non-rebase phases.

### 3. Alembic migration — single file covering three schema deltas

Generate via:

```bash
uv run alembic revision --autogenerate -m "CR-00021 rebase pipeline phase"
```

Inspect the autogen output and then **hand-edit** to match the three required deltas exactly — autogenerate will not produce the PG-enum `ALTER TYPE ... ADD VALUE` automatically, and it may emit a non-atomic CHECK drop/add. Final file must contain:

**In `upgrade()`:**

1. **Add the new PG enum value OUTSIDE the implicit transaction.** Follow the CR-00019 pattern:
   ```python
   with op.get_context().autocommit_block():
       op.execute("ALTER TYPE batch_item_status ADD VALUE IF NOT EXISTS 'migration_rebase_failed'")
   ```
   Use `IF NOT EXISTS` so the migration is re-runnable on partial-failure recovery.

2. **Recreate the CHECK constraint on `pending_migration_log.phase`** atomically:
   ```python
   op.drop_constraint("ck_pending_migration_log_phase", "pending_migration_log", type_="check")
   op.create_check_constraint(
       "ck_pending_migration_log_phase",
       "pending_migration_log",
       "phase IN ('dry_run', 'apply', 'rollback', 'rebase')",
   )
   ```

3. **Add the new column:**
   ```python
   op.add_column(
       "pending_migration_log",
       sa.Column("old_revision", sa.Text(), nullable=True,
                 comment="Previous down_revision before the rebase phase rewrote it"),
   )
   ```

**In `downgrade()`:**

1. Drop the column:
   ```python
   op.drop_column("pending_migration_log", "old_revision")
   ```

2. Restore the 3-value CHECK constraint:
   ```python
   op.drop_constraint("ck_pending_migration_log_phase", "pending_migration_log", type_="check")
   op.create_check_constraint(
       "ck_pending_migration_log_phase",
       "pending_migration_log",
       "phase IN ('dry_run', 'apply', 'rollback')",
   )
   ```

3. **Document the enum-label orphan:** add a module-level docstring and an in-function comment stating that Postgres does not support dropping an enum label; `'migration_rebase_failed'` is left as a dormant orphan after downgrade. No code change in `downgrade()` for the enum.

**Module docstring:** summarise the three deltas and the CR number. Mention the enum-orphan trade-off explicitly (matches CR-00019 precedent).

### 4. Schema documentation update

In `docs/IW_AI_Core_Database_Schema.md`:

- In the `batch_item_status` enum values list, add `migration_rebase_failed` with a one-line description: "Pre-merge rebase phase failed (e.g., git conflict) — batch is rejected without touching main. Queue is not frozen."
- In the `pending_migration_log` section:
  - Add `old_revision TEXT NULL` to the column list, with a one-line description.
  - Update the `ck_pending_migration_log_phase` CHECK description to list the four allowed values.

Keep the tone and structure matching the existing schema doc.

## Project Conventions

- Sync SQLAlchemy 2.0, `Mapped[]` declarative style; do NOT add `from __future__ import annotations` to `orch/db/models.py`.
- Driver is psycopg v3 (`postgresql+psycopg://`). Migration must be psycopg-compatible.
- Enum / constraint / index naming: `ck_*`, `uq_*`, `ix_*`, `fk_*`.
- `ALTER TYPE ... ADD VALUE` must run in an autocommit block — read CR-00019's migration end-to-end to see the exact pattern.
- Test containers must run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` — unchanged by this step.

## TDD Requirement

Schema-only step; full test suite is in S07. For S01 you must:

1. Confirm `alembic upgrade` + `downgrade` round-trip against a fresh testcontainer (the `pg_engine` fixture in `tests/conftest.py` exercises this automatically via `make test-integration`). The round-trip must:
   - Start at the current head on a fresh PG container.
   - Apply the new migration → CHECK includes `'rebase'`, column `old_revision` exists, enum includes `migration_rebase_failed`.
   - Downgrade → column gone, CHECK back to 3 values, enum label remains (expected per the Postgres limitation).
2. Confirm `Base.metadata.create_all()` on a fresh DB produces a schema consistent with the upgraded state — i.e., the new `BatchItemStatus` member is emitted as part of the enum and `PendingMigrationLog.old_revision` exists.

Do NOT write test files in this step — S07 owns the full test suite. Just verify upgrade/downgrade works before handoff.

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-integration` — must pass (the migration round-trip is exercised via the `pg_engine` fixture).
2. Run `make lint`, `make format`, `make typecheck` — must pass against your changes.
3. Report accurately in the JSON contract.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00021",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<hash>_cr_00021_rebase_pipeline_phase.py",
    "docs/IW_AI_Core_Database_Schema.md"
  ],
  "tests_passed": true,
  "test_summary": "integration X passed; upgrade/downgrade round-trip verified",
  "blockers": [],
  "notes": "migration revision hash: <hash>"
}
```
