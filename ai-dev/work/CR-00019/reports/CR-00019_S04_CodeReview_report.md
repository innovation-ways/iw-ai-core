# S04 Report: Final Code Review for CR-00019

## What was done

Performed holistic cross-agent final code review of CR-00019 (Selection-driven OSS Prepare with reviewable worktree lifecycle), reviewing S01 (Database), S03 (Backend) implementations together for integration correctness.

## Files changed (S01+S03)

| File | Change |
|------|--------|
| `orch/db/migrations/versions/9ef17911f546_cr_00019_add_awaiting_review_discarded_.py` | S01 - New migration: enum values + columns |
| `dashboard/services/oss_service.py` | S03 - Helpers, `_run_worktree` lifecycle, `discard_job`, `job_event_stream` |
| `orch/oss/persistence.py` | S03 - Added `rationale` field population |
| `docs/IW_AI_Core_Database_Schema.md` | S01 - Added Section 7 documenting CR-00019 extensions |

## Test Results

- **Lint**: PASS — no new errors in CR-00019 files (pre-existing errors in `migrations/versions/1fb2eb17b580_*.py` and `test_oss_dashboard_templates_extras.py` are unrelated)
- **Mypy**: PASS — no type errors in changed files
- **Unit tests**: PASS — all 11 unit tests pass
- **Integration tests**: 13 failures in `test_oss_dashboard_service.py` due to **out-of-sync test fixtures** (see CRITICAL finding below)

## Findings

### CR-00019-F01 — CRITICAL
- **Location**: `tests/integration/test_oss_dashboard_service.py:34-136` (and `test_oss_dashboard_templates_extras.py`)
- **Issue**: Integration test fixtures (`OSS_MIGRATION_SQL`) define the old schema without CR-00019 columns (`base_sha`, `branch_name`, `commit_sha`, `files_changed_summary`) and enum values (`awaiting_review`, `discarded`), and missing `rationale` on `oss_finding`
- **Impact**: All 13 integration tests fail with `ProgrammingError: column "base_sha" of relation "project_oss_job" does not exist`
- **Recommendation**: Update `OSS_MIGRATION_SQL` in both test files to include CR-00019 columns and enum values

### CR-00019-F02 — MEDIUM
- **Location**: `dashboard/services/oss_service.py:260-264, 346`
- **Issue**: When `base_sha` is `None` (git unavailable), an empty string is passed to `_git_commit_info`, producing an invalid git diff command (`git diff --stat ..sha`) that fails silently
- **Recommendation**: Add explicit check for `None`/`""` `base_sha` before calling git diff; set `files_changed_summary` to a marker indicating git unavailable

### CR-00019-F03 — MEDIUM
- **Location**: `dashboard/services/oss_service.py:509`
- **Issue**: `discard_job` is defined but not exposed via any HTTP router — users cannot discard jobs from the UI
- **Recommendation**: Wire `discard_job` to a dashboard endpoint (e.g., `POST /api/oss/jobs/{job_id}/discard`) or document as programmatic-only

### CR-00019-F04 — LOW
- **Location**: `dashboard/services/oss_service.py:367`
- **Issue**: Worktree cleanup condition excludes `awaiting_review` and `discarded` without explaining why
- **Recommendation**: Add comment explaining lifecycle: `awaiting_review` keeps worktree for manual review; `discarded` worktrees are cleaned up by `discard_job`

### CR-00019-F05 — INFO
- **Location**: `dashboard/services/oss_service.py:511`
- **Issue**: `discard_job` uses implicit lazy loading for `job.project` relationship after `session.commit()`
- **Recommendation**: Consider explicit `joinedload(ProjectOssJob.project)` for clarity

## Issues/Observations

1. **CRITICAL (F01)**: The integration test fixtures need updating before the full test suite can pass. This is the only blocking issue.
2. The `discard_job` not being exposed (F03) may be intentional if the design only intends programmatic discard, but if a UI discard button is needed, a router is required.
3. Pre-existing lint errors in `migrations/versions/*.py` and `test_oss_dashboard_templates_extras.py` are unrelated to CR-00019 changes.
