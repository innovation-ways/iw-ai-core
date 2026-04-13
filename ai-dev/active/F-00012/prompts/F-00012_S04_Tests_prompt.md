# F-00012_S04_Tests_prompt

**Work Item**: F-00012 — Project-Level Documentation System — AI Generation (Phase 2)
**Step**: S04
**Agent**: Tests

---

## Input Files

- `ai-dev/active/F-00012/F-00012_Feature_Design.md` — Design document (Acceptance Criteria + Boundary Behavior are your test specification)
- All S01–S03 implementation reports
- `tests/CLAUDE.md` — Test conventions (read first — critical)
- `tests/conftest.py` — Existing fixtures

## Output Files

- `tests/integration/test_doc_generation.py` — Integration tests for the full generation pipeline
- `tests/integration/test_doc_job_routes.py` — Dashboard route tests for generation endpoints
- `ai-dev/work/F-00012/reports/F-00012_S04_Tests_report.md` — Step report

## Context

You are writing integration tests for **F-00012: AI Documentation Generation**.

The key challenge: the daemon launches real agent processes. In integration tests, do NOT launch real claude-code agents. Instead, simulate the agent lifecycle by calling `iw doc-job-start` and `iw doc-job-done` CLI commands directly (and `iw doc-update` to write content), exactly as a real agent would. This gives full roundtrip coverage without requiring a running AI agent.

**CRITICAL**: NEVER connect to live DB. NEVER mock DB. Testcontainers only.

## Requirements

### 1. Job Lifecycle Roundtrip (`tests/integration/test_doc_generation.py`)

**Test: `test_full_job_lifecycle_success`**
```
1. Create ProjectDoc (via DocService)
2. POST /api/project/{id}/docs/{doc_id}/generate → assert 200, job_id returned
3. Assert DocGenerationJob exists with status=queued
4. Simulate agent: iw doc-job-start {job_id} --skill iw-doc-generator
5. Assert status=running, started_at set
6. Simulate agent: iw doc-update {project_id} {doc_id} --content "# Generated Doc\n\nContent." --generated-by skill:iw-doc-generator
7. Assert ProjectDoc.content updated, version incremented
8. Simulate agent: iw doc-job-done {job_id}
9. Assert status=completed, completed_at set, duration_seconds computed
```

**Test: `test_full_job_lifecycle_failure`**
```
1. Create job, start it
2. iw doc-job-done {job_id} --error "Source file not found"
3. Assert status=failed, error field set
4. Assert ProjectDoc.content unchanged (agent did not call doc-update)
```

**Test: `test_concurrent_job_limit`**
```
1. Create 2 jobs, start both (DocService.start_doc_job directly)
2. Create a 3rd job
3. Call DocJobPoller.poll() (with mocked subprocess)
4. Assert the 3rd job remains queued (not started)
5. Complete one of the 2 running jobs
6. Call DocJobPoller.poll() again
7. Assert 3rd job is now started
```

**Test: `test_stall_detection`**
```
1. Create a job and start it
2. Manually set started_at = now() - 11 minutes in DB
3. Call DocJobPoller.poll()
4. Assert job transitions to failed with error containing "timeout"
```

**Test: `test_generate_when_job_already_running_returns_409`**
```
1. Create a job, start it (status=running)
2. POST /api/project/{id}/docs/{doc_id}/generate
3. Assert 409 response
```

### 2. CLI Commands (`tests/integration/test_doc_generation.py`)

**Test: `test_doc_job_start_cli`** — CliRunner, assert JSON output and DB state  
**Test: `test_doc_job_done_cli`** — CliRunner, assert status=completed  
**Test: `test_doc_job_done_idempotent`** — twice → no error  
**Test: `test_doc_job_start_unknown_job`** — exit code 1  

### 3. SSE Route (`tests/integration/test_doc_job_routes.py`)

**Test: `test_sse_stream_emits_completed_event`**
```
1. Create and start a job
2. In a background thread: complete the job after 0.5s
3. Connect to SSE stream, collect events for 2s
4. Assert "completed" event was received
```

**Test: `test_status_poll_route`**
```
GET /api/project/{id}/docs/jobs/{job_id}/status
Assert: 200, JSON with correct status, job fields
```

**Test: `test_job_history_route`**
```
Create 3 jobs (1 completed, 1 failed, 1 queued)
GET /api/project/{id}/docs/{doc_id}/jobs
Assert: 200, HTML contains all 3 job entries
```

### 4. Boundary Tests

- `test_generate_doc_with_no_source_paths` — assert job is created (not blocked), job runs with empty context
- `test_skill_selection_technical` — assert `iw-doc-generator` selected for `technical` category
- `test_skill_selection_guide` — assert `iw-doc-system` selected for `guide` category
- `test_job_done_unknown_job_exits_1` — CliRunner, exit code 1

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass
2. `make test-integration` — pass
3. `make quality` — pass

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "Tests",
  "work_item": "F-00012",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_doc_generation.py",
    "tests/integration/test_doc_job_routes.py"
  ],
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
