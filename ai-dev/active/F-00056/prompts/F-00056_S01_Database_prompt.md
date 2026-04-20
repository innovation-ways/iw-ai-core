# F-00056_S01_Database_prompt

**Work Item**: F-00056 -- Work Item Execution Report — Retry Pattern & Pain-Point Visibility
**Step**: S01
**Agent**: database-impl

---

## Input Files

- `ai-dev/active/F-00056/F-00056_Feature_Design.md` -- Design document (read the Schema Addition, Database Changes, and Invariants sections carefully)
- `orch/db/models.py:533-571` -- existing `FixCycle` model (target of modification)
- `orch/db/migrations/versions/e5f6a7b8c9d0_add_log_content_to_step_runs.py` -- reference: most recent additive-column migration (pattern to mirror)
- `orch/CLAUDE.md` -- ORM conventions, migration conventions

## Output Files

- `ai-dev/active/F-00056/reports/F-00056_S01_Database_report.md` -- Step report

## Context

You are adding a single nullable column, `fix_summary TEXT`, to the `fix_cycles` table. This column will be populated by the fix agent's result payload (at end of fix cycle) with a 1-3 bullet summary of what changed and why, so downstream surfaces (markdown execution report and dashboard timeline) can tell the story of a retry.

Nothing else in the schema changes. This step is strictly additive and safe to deploy.

## Requirements

### 1. Add `fix_summary` mapped column on the `FixCycle` model

In `orch/db/models.py` (class `FixCycle`, currently at lines 533-571), add a new column after `fix_report` and before `status`:

```python
fix_summary: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    comment=(
        "Fix agent's 1-3 bullet summary of what changed and why; "
        "NULL for pre-F-00056 cycles or when the agent did not emit a summary"
    ),
)
```

Follow the exact style of sibling columns (Mapped type, `mapped_column(Text, ...)` kwargs, `comment=` wording). Do not reorder existing columns.

### 2. Generate an Alembic migration

From the repo root:

```bash
uv run alembic revision --autogenerate -m "add_fix_summary_to_fix_cycles"
```

Verify the generated file:

- Location: `orch/db/migrations/versions/<rev>_add_fix_summary_to_fix_cycles.py`
- `upgrade()` contains exactly one `op.add_column("fix_cycles", sa.Column("fix_summary", sa.Text(), nullable=True, comment=...))`
- `downgrade()` contains exactly one `op.drop_column("fix_cycles", "fix_summary")`
- No other schema operations are present (autogenerate can pick up noise; delete anything unrelated)
- `revision`, `down_revision`, `branch_labels`, `depends_on` are correctly set by alembic; do not hand-edit

If autogenerate produces anything other than these two operations, edit the migration to contain only them.

### 3. Apply the migration locally and verify

Run:

```bash
make db-migrate
```

Then verify the column exists with a one-off psql query (or equivalent Python check):

```bash
uv run python -c "from orch.db.session import SessionLocal; from sqlalchemy import text; \
  s = SessionLocal(); \
  print(s.execute(text(\"SELECT column_name, is_nullable, data_type FROM information_schema.columns WHERE table_name = 'fix_cycles' AND column_name = 'fix_summary'\")).fetchall())"
```

Expected output: one row with `fix_summary | YES | text`.

### 4. Do NOT backfill existing rows

Pre-existing `fix_cycles` rows keep `fix_summary = NULL`. Downstream code (S03) handles the NULL case. No data migration is required or permitted in this step.

### 5. Confirm no other model or migration files are touched

This step is schema-only. Do not modify `orch/daemon/`, `orch/cli/`, tests, or any other file outside `orch/db/models.py` and the new migration file.

## Project Conventions

Read the project's `CLAUDE.md` and `orch/CLAUDE.md` for:

- SQLAlchemy 2.0 `Mapped[]` declarative style (not the pre-2.0 `Column` pattern)
- Append-only discipline on `fix_cycles` (we UPDATE `fix_summary` at cycle completion; this is an accepted exception inside the cycle lifecycle, not an append rewrite)
- Migration naming: `<rev>_<snake_case_summary>.py`
- Migration location: `orch/db/migrations/versions/`
- Driver is `psycopg` v3; alembic config is in `alembic.ini` at repo root

## TDD Requirement

For a pure schema additive change, the test coverage comes in S09 (tests-impl). For S01 it is sufficient that:

1. The migration runs cleanly on an empty testcontainer DB (verified implicitly by the Test Verification step below running the existing test suite).
2. The downgrade runs cleanly back to the previous revision.

Verify downgrade locally:

```bash
uv run alembic downgrade -1
uv run alembic upgrade head
```

Both commands must complete without error.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit` -- all existing tests continue to pass
2. `make test-integration` -- existing integration tests pass against the migrated DB
3. `uv run ruff check orch/db/models.py orch/db/migrations/versions/<rev>_*.py`
4. `uv run mypy orch/db/models.py`

Do not report `tests_passed: true` unless all four commands return zero exit codes.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00056",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<rev>_add_fix_summary_to_fix_cycles.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "migration revision: <rev>"
}
```
