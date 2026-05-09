# CR-00038 S03 — Tests Report

## What Was Done

Added `tests/dashboard/test_docs_running_jobs.py` covering all 7 required test scenarios for the new `GET /project/{project_id}/api/docs/running-jobs` htmx fragment endpoint, plus the updated `POST /project/{project_id}/api/docs/{doc_id}/generate` response format.

## Files Changed

- **Created:** `tests/dashboard/test_docs_running_jobs.py` (403 lines)

## Test Cases Added

| # | Test | Scenario |
|---|------|----------|
| 1 | `TestRunningJobsEmpty::test_running_jobs_empty` | No running jobs → 200, no `docs-rjob-*` divs |
| 2 | `TestRunningJobsShowOne::test_running_jobs_shows_running` | One running job → row div with job_id, doc title, cancel button |
| 3 | `TestRunningJobsMultiple::test_running_jobs_multiple` | Two running jobs for same project → both rows appear |
| 4 | `TestRunningJobsCrossProjectIsolation::test_running_jobs_cross_project_isolation` | Project B's job does not leak into Project A's strip |
| 5 | `TestRunningJobsCompletedExcluded::test_running_jobs_completed_not_shown` | Completed job excluded from strip |
| 6 | `TestRunningJobsResearchExcluded::test_running_jobs_no_research_docs` | `doc_type=research` jobs excluded from strip |
| 7 | `TestGenerateResponseDisablesButton::test_generate_response_disables_button` | Generate POST → disabled button, `HX-Trigger: runningJobsReload` |

## Key Technical Decisions

### ProjectDoc fixture (`_make_project_doc`)
`tier` and `editorial_category` are NOT NULL columns with no Python-side defaults. All inline `ProjectDoc` constructions pass explicit `DocTier.semi_automated` and `EditorialCategory.technical` to satisfy the constraint.

### Cross-project isolation test
`DocGenerationJob` has a FK on `project_id` referencing `projects`. The test creates a real `Project` row for "proj-b" before inserting the job and doc, to avoid FK violations.

### Research exclusion test
SQLAlchemy was batching `doc_research` insert with `job_research` insert before `doc_research` flushed — causing the FK violation. Fixed by flushing `doc_research` before adding the job, ensuring correct insert ordering within the transaction.

### Generate endpoint job status
`create_doc_job()` creates jobs with `status=queued`; the daemon poller transitions them to `running`. The test asserts a job row was persisted (status agnostic) rather than asserting `status=running`, since that transition requires the daemon.

## Test Results

```
7 passed, 1 warning in 19.93s
```

No existing tests were broken (no `filter-pill` or `hx-vals` pill-button assertions found in the test suite).

## Notes

- The test file uses the `db_session` + `test_project` fixtures from `tests/dashboard/conftest.py` (which re-exports from `tests/integration/conftest.py`) — no live DB, no mock of the database.
- `TestClient` is configured with `raise_server_exceptions=True` to surface 500-level errors rather than returning a generic HTML body.
- Coverage check failure is expected: this test file alone does not bring total coverage to 46%; full-suite execution is owned by QV gate S10.