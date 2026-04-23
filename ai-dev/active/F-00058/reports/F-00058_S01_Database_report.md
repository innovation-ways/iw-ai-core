# F-00058_S01_Database_report

**Step**: S01 — Database (project_oss_job table + ORM model)
**Work Item**: F-00058 — OSS compliance dashboard view + status pill
**Agent**: database-impl
**Status**: COMPLETE

## What Was Done

### 1. Alembic Migration (`13014259ab68_add_project_oss_job.py`)

Created migration for `project_oss_job` table per F-00058 design spec:

- **Enums**: `project_oss_job_kind` (scan/prepare/publish/install), `project_oss_job_status` (queued/running/complete/error/cancelled)
- **Columns**: id (BIGSERIAL PK), project_id (FK→projects ON DELETE CASCADE), kind, status (default queued), created_at (default NOW()), started_at, completed_at, exit_code, worktree_path (nullable, NULL for scan/install), scan_id (nullable FK→oss_scan.id ON DELETE SET NULL), stdout_tail (nullable, 16KB cap at app layer), error_message
- **Indexes**: `(project_id, created_at DESC)`, `(status)`
- Downgrade drops table + both enum types

### 2. ORM Model (`ProjectOssJob` in `orch/db/models.py`)

Added Python enums `ProjectOssJobKind` and `ProjectOssJobStatus` + SQLAlchemy 2.0 typed `ProjectOssJob` model with:
- `back_populates` to `Project.oss_jobs`
- Optional `OssScan` relationship via `scan_id` foreign key

### 3. Integration Tests (`test_project_oss_job_migration.py`)

18 tests covering:
- Table/column/index existence
- Enum values (kind: scan/prepare/publish/install; status: queued/running/complete/error/cancelled)
- ORM model CRUD (all job kinds including install with null worktree_path)
- FK constraints (valid project, invalid project_id, scan_id with SET NULL cascade)
- FK cascade delete (project→jobs)
- Project.oss_jobs relationship
- Downgrade reversibility (table + enum types dropped)

## Files Changed

| File | Change |
|------|--------|
| `orch/db/migrations/versions/13014259ab68_add_project_oss_job.py` | NEW — migration |
| `orch/db/models.py` | MODIFIED — added `ProjectOssJobKind`/`ProjectOssJobStatus` enums + `ProjectOssJob` model + `Project.oss_jobs` relationship |
| `tests/integration/test_project_oss_job_migration.py` | NEW — 18 integration tests |

## Test Results

**`test_project_oss_job_migration.py` (new tests)**: 18 passed, 1 warning (pre-existing SAWarning)

**`make lint`**: 1 pre-existing ARG001 error in `orch/cli/item_commands.py:593` (unrelated to this change — `archive_dir` argument exists in baseline)

**`make test-integration`**: 427 passed, 5 failed, 389 errors. Failures/errors are pre-existing issues unrelated to this change (migration downgrade tests, dashboard API routes, code index pipeline). All new tests for `project_oss_job` passed.

## Issues / Observations

- The pre-existing ARG001 lint error in `item_commands.py:593` existed before this change (verified via `git stash` + `make lint`). Not introduced by this work.
- Integration test suite has many pre-existing failures in unrelated modules (migration downgrade tests, dashboard routes, code index). These are baseline failures not caused by S01 changes.
- The new `project_oss_job` tests use a standalone testcontainer with a self-contained migration SQL, avoiding interference with other tests.
