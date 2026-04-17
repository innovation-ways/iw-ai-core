# CR-00006 S04 — API Review

## Input Files

- `ai-dev/active/CR-00006/CR-00006_CR_Design.md`
- `ai-dev/active/CR-00006/prompts/CR-00006_S03_Api_prompt.md`
- `dashboard/routers/jobs_ui.py`
- `dashboard/routers/sse.py`
- `dashboard/app.py`

## Output Files

- `ai-dev/work/CR-00006/reports/S04_api_review.md`

## Context

**Work item**: CR-00006
**Step**: S04
**Agent**: api-review

Review the three new routes, the toast-map extension, and the router registration.

## Review Checklist

### `dashboard/routers/jobs_ui.py`

- [ ] Router prefix is `"/project/{project_id}"`, matching `code_ui.py`'s convention.
- [ ] Three routes registered: `GET /jobs`, `GET /jobs/fragment/table`, `GET /jobs/{job_type}/{job_id}`.
- [ ] `job_type` path parameter is typed as `Literal["code_mapping", "doc_generation", "batch_execution", "research"]` — invalid values return 422.
- [ ] Query parameters: `type` and `status` are list-valued (`Query()`), `page` has `ge=1` constraint, `sort_by` and `sort_dir` use `Literal` types.
- [ ] Missing project → HTTP 404 with `"Project not found"`.
- [ ] Missing job → HTTP 404 with `"Job not found"`.
- [ ] Invalid date format → HTTP 422 with an informative message.
- [ ] Unknown `type`/`status` query values → HTTP 422 (FastAPI/Pydantic enforced).
- [ ] List page renders `pages/project/jobs.html` with the exact context keys specified in the design.
- [ ] Fragment endpoint renders `fragments/jobs_table.html` — **does not** extend `base.html`.
- [ ] Detail page renders `pages/project/job_detail.html`.
- [ ] No business logic in routes — all aggregation work is delegated to `JobsAggregator`.
- [ ] No direct DB queries beyond `_get_project_or_404`.
- [ ] Template references match the file names S05 will create: `pages/project/jobs.html`, `pages/project/job_detail.html`, `fragments/jobs_table.html`.
- [ ] `ruff check dashboard/routers/jobs_ui.py` is clean.
- [ ] `mypy dashboard/routers/jobs_ui.py` is clean.

### `dashboard/routers/sse.py`

- [ ] `"code_map_completed"` is added to `_TOAST_EVENTS` exactly once.
- [ ] `"code_map_completed": "success"` is added to `_TOAST_SEVERITY` exactly once.
- [ ] No other sets/maps were touched — event is NOT added to `_RUNNING_UPDATE_EVENTS`, `_STATUS_UPDATE_EVENTS`, `_TEST_UPDATE_EVENTS`, or `_QUALITY_UPDATE_EVENTS` (it's purely a toast).
- [ ] `_WATCHED_EVENTS` union automatically includes the new event through the existing `|` composition.

### `dashboard/app.py`

- [ ] `from dashboard.routers import jobs_ui` is added in the correct alphabetical/grouped position.
- [ ] `app.include_router(jobs_ui.router)` is added alongside the other calls.
- [ ] No other imports or calls reordered.

### Route discovery smoke-test

Run:

```bash
uv run python -c "from dashboard.app import create_app; app = create_app(); paths = sorted([r.path for r in app.routes if 'jobs' in r.path]); [print(p) for p in paths]"
```

Expected three lines:

```
/project/{project_id}/jobs
/project/{project_id}/jobs/fragment/table
/project/{project_id}/jobs/{job_type}/{job_id}
```

### Cross-cutting

- [ ] No templates created in this step (S05 owns templates).
- [ ] No changes to `code_qa.py`, `qa.py`, `aggregator.py`, or any models.
- [ ] No tests written.

## Signal completion

If correct:

```bash
iw step-done CR-00006 S04 --summary "API review passed: three routes registered with correct typing and error contracts, sse.py toast map extended with code_map_completed=success, jobs_ui router wired in dashboard/app.py"
```

If issues found:

```bash
iw step-fail CR-00006 S04 --reason "<CRITICAL/HIGH findings summary>"
```
