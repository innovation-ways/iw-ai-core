# F-00056_S02_CodeReview_prompt

**Work Item**: F-00056 -- Work Item Execution Report — Retry Pattern & Pain-Point Visibility
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/F-00056/F-00056_Feature_Design.md` -- Design document (read Database Changes, Invariants 4, 11)
- `ai-dev/active/F-00056/reports/F-00056_S01_Database_report.md` -- S01 implementation report
- `orch/db/models.py` -- modified `FixCycle` class
- The new Alembic migration file named in the S01 report

## Output Files

- `ai-dev/active/F-00056/reports/F-00056_S02_CodeReview_report.md` -- Review report

## Context

You are reviewing S01's schema addition: a single nullable `fix_summary TEXT` column on `fix_cycles`, the mapped `FixCycle.fix_summary` field on the ORM, and the Alembic migration.

## Review Checklist

### 1. Architecture Compliance

- Column is `nullable=True` (Invariant 11).
- `Mapped[str | None]` uses the 2.0 declarative style; matches sibling columns.
- Column placement is sensible (near `fix_report`).
- Migration file name matches the `<rev>_<snake_case>` pattern used in prior migrations.
- No unrelated autogenerate noise in the migration (only `op.add_column` / `op.drop_column`).

### 2. Code Quality

- `comment=` on the column matches the wording in the S01 prompt.
- No hand-edits to `revision` / `down_revision` / `branch_labels` / `depends_on`.
- `downgrade()` correctly mirrors `upgrade()`.

### 3. Project Conventions

- Read project `CLAUDE.md` rules:
  - `psycopg` v3 (not `psycopg2`)
  - SQLAlchemy 2.0 `Mapped[]`
  - Migration location and naming

### 4. Security

- No PII, secrets, or user-provided data stored unredacted — `fix_summary` is AI-generated free text and stored verbatim; confirm no injection or escape concerns downstream (renderers must handle it).

### 5. Testing

- Existing tests continue to pass after migration runs.
- No new tests are required in S01 (coverage is added in S09) — do not flag "missing tests for S01" as HIGH; S01's test burden is deferred.

## Test Verification (NON-NEGOTIABLE)

Before submitting:

1. `make test-unit`
2. `make test-integration`
3. `uv run ruff check orch/db/`
4. `uv run mypy orch/db/`

Apply the migration forward and backward (`alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head`) and confirm no errors.

## Severity Levels

See template; use the standard 5-level scale.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "F-00056",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
