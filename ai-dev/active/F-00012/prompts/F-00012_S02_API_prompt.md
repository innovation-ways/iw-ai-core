# F-00012_S02_API_prompt

**Work Item**: F-00012 — Project-Level Documentation System — AI Generation (Phase 2)
**Step**: S02
**Agent**: API

---

## Input Files

- `ai-dev/active/F-00012/F-00012_Feature_Design.md` — Design document
- `ai-dev/work/F-00012/reports/F-00012_S01_Backend_report.md` — S01 report
- `orch/cli/doc_commands.py` — Existing doc CLI (from F-00011)
- `orch/cli/step_commands.py` — Model for new CLI commands
- `dashboard/routers/sse.py` — Existing SSE patterns
- `dashboard/routers/docs.py` — Existing docs router (from F-00011)
- `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`

## Output Files

- `orch/cli/doc_commands.py` — Extended with `doc-job-start` and `doc-job-done` commands
- `dashboard/routers/docs.py` — Extended with generate, SSE, status, and job history routes
- `ai-dev/work/F-00012/reports/F-00012_S02_API_report.md` — Step report

## Context

You are implementing the API and CLI layer for **F-00012: AI Documentation Generation**.

This step adds the CLI commands that agents call to report job lifecycle, and the dashboard routes that power real-time progress streaming and job management. Study `dashboard/routers/sse.py` before writing any SSE code — match the exact pattern.

## Requirements

### 1. CLI: `iw doc-job-start`

Add to `orch/cli/doc_commands.py`:

```
iw doc-job-start JOB_ID [--pid INTEGER] [--skill TEXT]
```

- Calls `DocService.start_doc_job(job_id, pid=..., skill_used=...)`
- On success: print JSON `{"job_id": "...", "status": "running"}` to stdout, exit 0
- If job not found: exit 1
- If job not in queued state: exit 2 (idempotent — already running is not an error, just exit 0)

### 2. CLI: `iw doc-job-done`

Add to `orch/cli/doc_commands.py`:

```
iw doc-job-done JOB_ID [--error TEXT]
```

- Calls `DocService.complete_doc_job(job_id, error=...)`
- On success: print JSON `{"job_id": "...", "status": "completed|failed"}` to stdout, exit 0
- If job not found: exit 1
- Idempotent: calling on already-completed job → exit 0 without error

### 3. Dashboard Route: POST `/api/project/{id}/docs/{doc_id}/generate`

- Creates a `DocGenerationJob` via `DocService.create_doc_job()`
- Returns htmx-compatible HTML fragment that replaces the Generate button with a spinner
- Adds `HX-Trigger` response header: `{"docJobCreated": {"job_id": "...", "doc_id": "..."}}` for htmx event dispatch
- If a job is already running for this doc: return 409 with "Generation already in progress" message

### 4. Dashboard Route: GET `/api/project/{id}/docs/jobs/{job_id}/stream`

SSE endpoint following the exact pattern of `dashboard/routers/sse.py`.

Events emitted:
- `data: {"event": "status", "status": "running", "job_id": "..."}` — every 2 seconds while running
- `data: {"event": "completed", "status": "completed", "doc_id": "..."}` — on completion
- `data: {"event": "failed", "status": "failed", "error": "...", "doc_id": "..."}` — on failure

Implementation: poll `DocService` every 2 seconds; emit status event; break loop on `completed` or `failed`. Respect SSE best practices — set `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Clean up generator on client disconnect.

Timeout: stop streaming after 15 minutes (emit `{"event": "timeout"}` and close).

### 5. Dashboard Route: GET `/api/project/{id}/docs/jobs/{job_id}/status`

Simple JSON poll endpoint for non-SSE clients:

```json
{
  "job_id": "...",
  "status": "queued|running|completed|failed",
  "started_at": "...",
  "completed_at": "...",
  "duration_seconds": 42,
  "skill_used": "iw-doc-generator",
  "error": null
}
```

### 6. Dashboard Route: GET `/api/project/{id}/docs/{doc_id}/jobs`

Returns htmx fragment: `docs_job_history.html` listing the last 10 `DocGenerationJob` records for this doc, ordered by `requested_at DESC`.

### 7. Dashboard Route: GET `/api/project/{id}/docs/{doc_id}/card`

Returns htmx fragment: a single `docs_card.html` for the given doc. Used by the frontend to refresh a card after generation completes (triggered via JavaScript on SSE `completed` event). Must return the same card fragment structure as the library page card loop.

## Project Conventions

- Read `dashboard/CLAUDE.md` before writing routes
- Match session injection pattern of existing docs.py routes
- All htmx routes must return HTML fragments (not full pages)
- SSE must follow the exact same structure as `dashboard/routers/sse.py`

## TDD Requirement

Tests in `tests/unit/test_doc_job_commands.py`:
- `test_doc_job_start_transitions_to_running` — CliRunner, assert exit 0 and JSON
- `test_doc_job_start_already_running_idempotent` — assert exit 0
- `test_doc_job_done_marks_completed` — assert exit 0 and status=completed
- `test_doc_job_done_with_error_marks_failed` — assert status=failed and error stored
- `test_doc_job_done_idempotent` — twice → exit 0

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all tests pass
2. `make quality` — ruff + mypy pass

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "API",
  "work_item": "F-00012",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/cli/doc_commands.py",
    "dashboard/routers/docs.py",
    "tests/unit/test_doc_job_commands.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
