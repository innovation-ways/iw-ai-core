# F-00058_S02_CodeReview_report

**Step**: S02 — Code Review (reviewing S01 database-impl)
**Work Item**: F-00058 — OSS compliance dashboard view + status pill
**Agent**: code-review-impl
**Status**: PASS

## What Was Done

Reviewed the S01 database implementation against the F-00058 design spec and the S02 review checklist. Verified:

1. **Migration** (`13014259ab68_add_project_oss_job.py`): Table, enums, indexes, FK constraints, downgrade path.
2. **ORM Model** (`ProjectOssJob` in `orch/db/models.py`): SQLAlchemy 2.0 typed syntax, enum mappings, relationships.
3. **Integration Tests** (`test_project_oss_job_migration.py`): 18 tests covering schema, ORM, FK constraints, cascade deletes, downgrade.

## Review Checklist Results

| Check | Result |
|-------|--------|
| `project_oss_job` schema matches design | ✅ PASS |
| `scan_id` uses `ON DELETE SET NULL` | ✅ PASS (`migration:91`, `models:1439`) |
| `project_id` uses `ON DELETE CASCADE` | ✅ PASS (`migration:90`, `models:1438`) |
| Enum names match PG type names | ✅ PASS (`project_oss_job_kind`, `project_oss_job_status`) |
| `kind` includes all 4 values (scan/prepare/publish/install) | ✅ PASS |
| `stdout_tail` is TEXT (not TEXT[]/JSON) | ✅ PASS (`migration:80-84`, `models:1427-1429`) |
| SQLAlchemy 2.0 typed syntax | ✅ PASS (`Mapped[]`, `mapped_column`) |
| Matches `models.py` style for neighboring models | ✅ PASS |
| Testcontainer used (no live DB) | ✅ PASS (line 184: `replace("postgresql+psycopg2://", "postgresql+psycopg://")`) |
| FTS trigger installed after `create_all()` | ✅ PASS (lines 203-209) |
| Migration test covers table + enums + indexes + downgrade | ✅ PASS (18 tests) |

## Test Results

**`test_project_oss_job_migration.py`**: 18 passed, 1 pre-existing SAWarning (unrelated to this change).

**`make lint`**: 1 pre-existing ARG001 error in `orch/cli/item_commands.py:593` (`archive_dir` argument unused) — verified pre-existing via S01 report, not introduced by this work.

## Issues / Observations

- **Pre-existing lint error** (ARG001 in `item_commands.py:593`) exists in baseline and is unrelated to F-00058.
- All S01 `project_oss_job` tests pass cleanly. No new issues found.
- The `SAWarning: transaction already deassociated from connection` on one test is a pre-existing fixture cleanup warning, not introduced by this change.

## Verdict

**PASS** — Zero CRITICAL/HIGH/MEDIUM_FIXABLE findings. S01 implementation is correct and compliant with the design spec.
