# CR-00038 S03 — Tests

**Work Item**: CR-00038 — Docs View: Filter Bar Redesign + Running-Jobs Strip + Spinner Fix
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Tests use testcontainers only — never connect to the live DB on port 5433. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this CR.

## Context

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, and `tests/CLAUDE.md` before starting. Key rules:
- Tests NEVER connect to the live DB (port 5433) — use testcontainers only.
- NEVER call `importlib.reload(orch.config)` — use `monkeypatch.delenv()` instead.
- NEVER mock the database in integration tests.
- MUST replace psycopg2 URLs: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- MUST run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- Dashboard integration tests use `TestClient` from `dashboard/app.py`.

## Objective

Add dashboard integration tests for the new `GET /api/docs/running-jobs` endpoint, and update any existing tests that now fail because they assert the old pill-button filter markup.

## Test File

Add tests to `tests/dashboard/test_docs.py` (or the appropriate existing test file — check `tests/dashboard/` for the correct location). Look at existing patterns in that file for how `TestClient`, DB fixtures, and project/doc creation helpers are set up.

## New Tests to Add

### 1. `test_running_jobs_empty`

**Scenario**: No running jobs for the project.

```
Given a project and zero DocGenerationJob rows with status=running for that project
When GET /project/{project_id}/api/docs/running-jobs
Then response is 200
And the HTML body does NOT contain any job row (the strip is empty / no <div id="docs-rjob-">)
```

### 2. `test_running_jobs_shows_running`

**Scenario**: One running job for the project.

```
Given a project, a Doc record, and a DocGenerationJob with status=running for that doc
When GET /project/{project_id}/api/docs/running-jobs
Then response is 200
And the HTML body contains a div with id="docs-rjob-{job_id}"
And the doc title is present in the response body
And a cancel button with hx-delete targeting the job cancel endpoint is present
```

### 3. `test_running_jobs_multiple`

**Scenario**: Multiple running jobs for the same project.

```
Given a project, two Docs, and two DocGenerationJobs both with status=running
When GET /project/{project_id}/api/docs/running-jobs
Then response is 200
And the HTML body contains two docs-rjob divs, one per job
```

### 4. `test_running_jobs_cross_project_isolation`

**Scenario**: Running job from a different project is not leaked.

```
Given two projects (A and B), each with a running DocGenerationJob
When GET /project/A/api/docs/running-jobs
Then the response contains only the job for project A, not project B's job
```

### 5. `test_running_jobs_completed_not_shown`

**Scenario**: Completed jobs are excluded.

```
Given a project with one DocGenerationJob with status=completed and one with status=running
When GET /project/{project_id}/api/docs/running-jobs
Then only the running job row appears in the response
```

### 6. `test_running_jobs_no_research_docs`

**Scenario**: Running jobs for research docs are excluded from the strip.

```
Given a project with a research Doc (doc_type=research) and a running DocGenerationJob for it,
     and a non-research Doc (doc_type=module) with a running DocGenerationJob
When GET /project/{project_id}/api/docs/running-jobs
Then the response contains only the non-research job row (docs-rjob-{non_research_job_id})
And the research job row (docs-rjob-{research_job_id}) is NOT present
```

### 7. `test_generate_response_disables_button`

**Scenario**: The generate POST returns a disabled button (not the old spinner fragment).

```
Given a project and a Doc with status=planned (so Generate button would show)
When POST /project/{project_id}/api/docs/{doc_id}/generate
Then response is 200
And the response HTML contains a <button disabled ...> element
And the response HTML does NOT contain "docs_generate_running" or "animate-spin w-4 h-4" as sole content (no full spinner-only fragment)
And the HX-Trigger response header contains "runningJobsReload"
And a DocGenerationJob row with status=running is created in the DB
```

### 7. Update Any Broken Existing Tests

Search `tests/dashboard/test_docs.py` for assertions that reference:
- CSS class `filter-pill`
- Text patterns like `"Type:"` adjacent to pill buttons
- `hx-vals='{"doc_type"` in template assertions

For each such assertion, update it to match the new `<select>` markup. Replace pill-specific assertions with equivalent select-based ones (e.g., assert `<select name="doc_type">` is present instead of `filter-pill` buttons).

## Test Quality: Semantic Correctness (I003 Lesson)

### 5. CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- **BAD**: `assert "docs-rjob" in response.text` (shape only)
- **BAD**: `assert response.status_code == 200` *alone* (does not prove the job row was rendered)
- **GOOD**: `assert f'id="docs-rjob-{job.id}"' in response.text` (semantic — verifies specific job ID)
- **GOOD**: `assert doc.title in response.text` (semantic — verifies specific doc title is present)
- **GOOD**: `assert f'id="docs-rjob-{other_job.id}"' not in response.text` (semantic — verifies other project's job is absent)

## Running Tests

After writing the new tests, run only the target file:

```bash
uv run pytest tests/dashboard/test_docs.py -v
```

All new and updated tests must pass. Full-suite execution (`make test-integration`) is owned by the downstream QV gate (S10) — do NOT run it here.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "CR-00038",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_docs.py"
  ],
  "tests_passed": true,
  "test_summary": "8 new tests added; N existing tests updated",
  "blockers": [],
  "notes": ""
}
```
