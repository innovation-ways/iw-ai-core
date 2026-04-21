# F-00057_S02_CodeReview_prompt

**Work Item**: F-00057 — `iw oss` CLI + DB persistence
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/F-00057/F-00057_Feature_Design.md` — Design document
- `ai-dev/active/F-00057/reports/F-00057_S01_Database_report.md` — S01 report
- All files listed in the S01 report's `files_changed` (migration + `orch/db/models.py` + migration test)

## Output Files

- `ai-dev/active/F-00057/reports/F-00057_S02_CodeReview_report.md` — Review report

## Context

Review S01's migration + ORM models for F-00057. The feature adds persistence for OSS compliance scan results.

## Review Checklist

### 1. Architecture Compliance

- Does the migration exactly match the design doc's *Database Changes* section (columns, FKs, indexes, enum values)?
- Do ORM class names / field names match the migration?
- Is the `Project` model change additive (does not break existing code that reads `Project` rows)?
- Are relationships declared with correct `cascade="all, delete-orphan"` on the project → scan and scan → (finding | tool_run) edges?

### 2. Code Quality

- Enum names in Python match the PostgreSQL enum-type names (`ossscan_status`, etc.).
- JSONB columns use `postgresql.JSONB` (not generic `JSON`).
- `server_default` set for defaults so existing rows satisfy NOT NULL on the added `oss_enabled` column.
- Migration downgrade reverses in correct order (child tables first, then enums, then column).
- Index definitions include the `DESC` on `started_at` where the design specifies.
- No unused imports, no stray debug prints, no commented-out blocks.

### 3. Project Conventions

- SQLAlchemy 2.0 typed style (`Mapped[...]` + `mapped_column(...)`) matching neighboring models.
- Python field naming: any field that would collide with SQLAlchemy reserved names (e.g., `metadata`) is renamed — per CLAUDE.md hard rule.
- Naming: snake_case columns, singular table names per existing convention.

### 4. Security

- No hardcoded credentials or DB URLs.
- No schema grants to non-owner roles introduced.

### 5. Testing

- `tests/integration/test_oss_migration.py` exists and asserts:
  - All three tables exist after migration upgrade.
  - `project.oss_enabled` column exists and defaults to `false`.
  - Enum values match spec exactly.
  - Indexes present.
  - Downgrade drops all objects cleanly.
- Test uses testcontainer Postgres (NOT the live DB on port 5433) per `tests/CLAUDE.md`.
- Test applies `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` if the test path uses that helper (per CLAUDE.md).

## Test Verification (NON-NEGOTIABLE)

Before submitting:

1. Run `make test-integration` — must pass.
2. Run `make lint` — must pass.
3. Report results accurately.

## Severity Levels

Use the project standard table (CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW).

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00057",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
