# F-00058_S02_CodeReview_prompt

**Work Item**: F-00058
**Step Being Reviewed**: S01 (database-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/F-00058/F-00058_Feature_Design.md`
- `ai-dev/active/F-00058/reports/F-00058_S01_Database_report.md`
- Files listed in S01 report

## Output Files

- `ai-dev/active/F-00058/reports/F-00058_S02_CodeReview_report.md`

## Review Checklist

### 1. Architecture Compliance
- `project_oss_job` schema matches the design's *Database Changes* section exactly.
- `scan_id` uses `ON DELETE SET NULL` (not CASCADE — jobs persist even after scans are purged).
- `project_id` uses `ON DELETE CASCADE`.

### 2. Code Quality
- Enum names match PG enum type names.
- Monotonic status progression is documented (even if not enforced at DB level).
- `stdout_tail` column type is TEXT (not TEXT[], not JSON).

### 3. Conventions
- SQLAlchemy 2.0 typed syntax.
- Matches `orch/db/models.py` style for neighboring models.

### 4. Testing
- Migration test in `tests/integration/test_project_oss_job_migration.py` covers table + enums + indexes + downgrade.
- Testcontainer used per CLAUDE.md (no live DB).
- FTS trigger installed after create_all().

## Test Verification (NON-NEGOTIABLE)

`make test-integration` + `make lint` pass.

## Review Result Contract

Standard JSON. `verdict: pass` only when zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
