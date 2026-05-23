# CR-00078_S01_Database_prompt

**Work Item**: CR-00078 -- Per-batch ignore overlap & force-start
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits
(Standard policy. Testcontainers in pytest fixtures are exempt.)

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade head` / `alembic downgrade` / `alembic stamp` against the live orchestration DB. Your job is to **write** the revision file. The daemon applies it during merge. Allowed: `alembic revision --autogenerate -m "..."`, `alembic history`, `alembic show`, `alembic current` (read-only), and inside testcontainer fixtures.

## Input Files

- `ai-dev/active/CR-00078/CR-00078_CR_Design.md` (§1, §AC7, "Database Changes")
- `orch/db/models.py` — model module
- `orch/db/migrations/env.py`, recent `versions/` files for the alembic conventions used in this repo
- `docs/IW_AI_Core_Database_Schema.md` — composite PK style

## Output Files

- `orch/db/models.py` — add `BatchOverlapIgnore` model
- `orch/db/migrations/versions/<rev>_cr_00078_add_batch_overlap_ignore.py` — new migration
- `ai-dev/active/CR-00078/reports/CR-00078_S01_Database_report.md`

## Requirements

### 1. ORM model

Add `BatchOverlapIgnore` to `orch/db/models.py` (SQLAlchemy 2.0 `Mapped[]` declarative style — match the conventions of existing models like `BatchItem`).

```python
class BatchOverlapIgnore(Base):
    __tablename__ = "batch_overlap_ignore"

    project_id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String, primary_key=True)
    held_item_id: Mapped[str] = mapped_column(String, primary_key=True)
    blocking_item_id: Mapped[str] = mapped_column(String, primary_key=True)
    file_pattern: Mapped[str] = mapped_column(String, primary_key=True)

    ignored_by: Mapped[str] = mapped_column(String, nullable=False)
    ignored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ("project_id", "batch_id"),
            ("batches.project_id", "batches.id"),
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ("project_id", "batch_id", "held_item_id"),
            ("batch_items.project_id", "batch_items.batch_id", "batch_items.work_item_id"),
            ondelete="CASCADE",
        ),
    )
```

- Match the import style used by other models (`from sqlalchemy import ...`, `from sqlalchemy.orm import Mapped, mapped_column`).
- Use `datetime` with `timezone=True` — check what other timestamp columns in the repo use; match exactly.
- Place the model near `BatchItem` for logical grouping.
- Register no relationship() back-refs unless other models in the repo do (most don't — composite PKs make relationship() unwieldy).

### 2. Alembic migration

Generate the migration:

```bash
uv run alembic revision --autogenerate -m "CR-00078 add batch_overlap_ignore"
```

Then **inspect the generated `upgrade()` / `downgrade()`** carefully:

- `op.create_table("batch_overlap_ignore", ...)` with the five PK columns + `ignored_by` + `ignored_at` (with `server_default=sa.func.now()`) + nullable `reason` Text.
- The composite PK declared via `sa.PrimaryKeyConstraint("project_id", "batch_id", "held_item_id", "blocking_item_id", "file_pattern")`.
- Both `sa.ForeignKeyConstraint(...)` with `ondelete="CASCADE"`. **Autogen often misses composite FKs to non-`id` columns — verify both FKs are present and correct. If missing, add them by hand.**
- `downgrade()` is `op.drop_table("batch_overlap_ignore")`.
- The revision's `down_revision` points at the current head; `revision` is a fresh hash.
- No incidental changes to other tables (autogen sometimes wants to "normalise" unrelated tables — revert any such drift).

### 3. Migration round-trip check (mandatory)

Run:

```bash
make migration-check
```

It must pass cleanly: upgrade from base, parity vs `Base.metadata.create_all()`, and downgrade-then-upgrade round-trip. If it fails, fix the migration (most common: missing FK or wrong column type) until it passes. Capture the passing output line in your report.

## TDD RED Evidence

`tdd_red_evidence`: `"n/a — schema-only step; behavioural tests for the model live in S10 (test_batch_overlap_ignore.py). The migration round-trip itself is exercised by `make migration-check` (S03) and `make test-integration` (S17)."`

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`
4. **`make migration-check`** (mandatory for any step that touches `orch/db/migrations/versions/`)

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00078",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<rev>_cr_00078_add_batch_overlap_ignore.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "make migration-check: PASSED (upgrade + drift + round-trip)",
  "tdd_red_evidence": "n/a — schema-only step; behavioural tests in S10",
  "blockers": [],
  "notes": "Both FKs verified present in the generated migration."
}
```
