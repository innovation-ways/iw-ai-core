# CR-00014_S01_Database_prompt

**Work Item**: CR-00014 — Orchestration DB instance-identity fingerprint
**Step**: S01
**Agent**: database-impl

---

## Input Files

- `ai-dev/active/CR-00014/CR-00014_CR_Design.md` — Design document (Desired Behavior, Database Changes, AC4, AC5)
- `orch/db/models.py` — existing ORM models (match convention: SQLAlchemy 2.0 `Mapped[]` style; composite PKs; `event_metadata` reserved-word gotcha)
- `orch/db/migrations/versions/a1b2c3d4e5f6_initial_schema.py` — reference for extension declarations + ENUM conventions
- `orch/db/migrations/versions/` — latest head is `824e6e6f34ee`; chain your revision from there
- `CLAUDE.md`, `orch/CLAUDE.md`, `tests/CLAUDE.md` — project conventions and hard rules

## Output Files

- `ai-dev/active/CR-00014/reports/CR-00014_S01_Database_report.md` — step report
- `orch/db/migrations/versions/{hash}_add_iw_core_instance.py` — new migration (hash from `iw migration-lock` / alembic)
- `orch/db/models.py` — add `IwCoreInstance` model

## Context

You're creating the schema for the orchestration DB's instance-identity fingerprint. Read the design doc first — in particular "Desired Behavior" points 1 + 7, and AC4 + AC5. Then read `orch/CLAUDE.md` for ORM style and `tests/CLAUDE.md` for the FTS-trigger rule that applies to `create_all()` paths.

## Migration-lock pre-flight

At design time the migration lock was held by F-00058, but F-00058's S01 was killed on 2026-04-22 and the lock is stale. Before calling `uv run iw migration-lock`:

1. Run `uv run iw migration-lock status`. If it's held by F-00058 (stale), run `uv run iw migration-lock release --item F-00058 --force` (check CLI help for exact flag — if no force-release exists, escalate as a blocker).
2. Then acquire the lock under CR-00014: `uv run iw migration-lock acquire --item CR-00014`.
3. Release it at the end of the step via `uv run iw migration-lock release --item CR-00014`.

## Requirements

### 1. Alembic migration

Create `orch/db/migrations/versions/{hash}_add_iw_core_instance.py`:

- `down_revision = "824e6e6f34ee"`
- Upgrade:
  - `CREATE EXTENSION IF NOT EXISTS pgcrypto;` (check the initial migration first — if pgcrypto is already declared there, no need; but `CREATE EXTENSION IF NOT EXISTS` is safe to repeat).
  - Create table `iw_core_instance`:
    - `id SMALLINT PRIMARY KEY` with a **check constraint** `CHECK (id = 1)` so no second row can ever exist.
    - `instance_id UUID NOT NULL`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - `comment` on the table explaining its purpose ("Orchestration DB identity fingerprint — see CR-00014").
  - Seed a row: `INSERT INTO iw_core_instance (id, instance_id) VALUES (1, gen_random_uuid()) ON CONFLICT (id) DO NOTHING;`
- Downgrade:
  - `DROP TABLE iw_core_instance;` (pgcrypto extension is shared — do NOT drop it on downgrade).
- Autogenerate friendliness: the migration must be written such that `alembic revision --autogenerate` from a fresh DB produces an empty diff afterwards. This means the ORM model must match exactly (see §2).

### 2. ORM model

Add to `orch/db/models.py`:

```python
class IwCoreInstance(Base):
    __tablename__ = "iw_core_instance"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_iw_core_instance_single_row"),
        {"comment": "Orchestration DB identity fingerprint — see CR-00014"},
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    instance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- Match existing import style in `models.py` (look at `Project`, `MigrationLock`, etc. for imports used). If `uuid` or `UUID`-as-SQL-type aren't imported yet, add the minimum imports.
- Place the class near `MigrationLock` — same "singleton/infrastructure" neighbourhood.
- No relationships, no FKs. This is a standalone table.

### 3. Do NOT forget FTS

`tests/CLAUDE.md` says: after `Base.metadata.create_all()`, test fixtures must run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`. Your changes don't add any FTS, but do NOT remove or reorder those constants in `models.py`. Sanity-check that the test fixture in `tests/conftest.py` still runs them after your model addition — it should, since adding a model doesn't affect the existing `FTS_FUNCTION_SQL`/`FTS_TRIGGER_SQL` constants.

## Project Conventions

Read `orch/CLAUDE.md` for:

- SQLAlchemy 2.0 typed `Mapped[]` style (NOT legacy `Column(...)` assignments to class attributes without typing).
- `DaemonEvent.metadata` lesson: never name a column `metadata` on a `DeclarativeBase` subclass — not applicable here but reinforces "check for reserved names".
- psycopg v3 driver in tests (`postgresql+psycopg://`), not psycopg2.
- Migration files use `__future__` annotations + `from collections.abc import Sequence` pattern.

## TDD Requirement

Follow Red–Green–Refactor:

1. **RED**: write `tests/integration/test_iw_core_instance_migration.py` (new file). It should:
   - Spin a testcontainer, run `alembic upgrade head`, assert: table exists with exactly one row, `instance_id` is a valid UUID v4, check constraint exists.
   - Assert a second-row INSERT raises `IntegrityError` (proves the CHECK constraint).
   - Round trip: `alembic downgrade -1` drops the table; `alembic upgrade head` re-creates it with a **new** UUID.
2. **GREEN**: write the migration + ORM model until that test passes.
3. **REFACTOR**: clean up imports, comments, naming.

Use psycopg v3 URL: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")` (see `tests/conftest.py` pattern).

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — pass (your new test + all existing).
2. `make lint` — pass.
3. Do NOT report `tests_passed: true` unless every integration test passes.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00014",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/migrations/versions/{hash}_add_iw_core_instance.py",
    "orch/db/models.py",
    "tests/integration/test_iw_core_instance_migration.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "New alembic head is {hash}. Migration lock released. UUID is seeded per-deploy; different testcontainer runs produce different UUIDs — that's intentional."
}
```

## Lifecycle commands

Start: `uv run iw step-start CR-00014 --step S01`

On success:
```bash
mkdir -p ai-dev/active/CR-00014/reports
uv run iw step-done CR-00014 --step S01 --report ai-dev/active/CR-00014/reports/CR-00014_S01_Database_report.md
```

On failure:
```bash
uv run iw step-fail CR-00014 --step S01 --reason "<brief reason>"
```
