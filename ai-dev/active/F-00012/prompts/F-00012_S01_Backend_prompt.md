# F-00012_S01_Backend_prompt

**Work Item**: F-00012 — Project-Level Documentation System — AI Generation (Phase 2)
**Step**: S01
**Agent**: Backend

---

## Input Files

- `ai-dev/active/F-00012/F-00012_Feature_Design.md` — Design document (read fully)
- `ai-dev/active/F-00011/F-00011_Feature_Design.md` — F-00011 design (Phase 1 context)
- `orch/daemon/` — Existing daemon architecture (read all files before writing anything)
- `orch/doc_service.py` — DocService from F-00011
- `orch/db/models.py` — DocGenerationJob model from F-00011
- `executor/CLAUDE.md` — Agent executor patterns
- `CLAUDE.md` — Project rules

## Output Files

- `orch/db/migrations/versions/{timestamp}_add_doc_job_agent_columns.py` — Migration for new columns
- `orch/db/models.py` — Add `agent_pid`, `skill_used`, `duration_seconds` columns to `DocGenerationJob`
- `orch/daemon/doc_job_poller.py` — New daemon component: `DocJobPoller` class
- `orch/doc_service.py` — Extended with job lifecycle methods
- `ai-dev/work/F-00012/reports/F-00012_S01_Backend_report.md` — Step report

## Context

You are implementing the daemon backend for **F-00012: AI Documentation Generation**.

The core job: after Phase 1 established the `DocGenerationJob` table and `DocService`, this phase makes the daemon watch for queued jobs, launch agents, and track completion. Read the existing daemon code thoroughly — understand how batches are polled, how agents are launched, and how job state is managed. Mirror those patterns exactly for doc jobs.

## Requirements

### 1. Alembic Migration

Add three columns to `doc_generation_jobs`:
- `agent_pid` — `Integer`, nullable: PID of the launched agent process
- `skill_used` — `String(100)`, nullable: which skill was invoked (e.g., `"iw-doc-generator"`)
- `duration_seconds` — `Integer`, nullable: wall-clock seconds from `started_at` to `completed_at`

Generate migration: `uv run alembic revision --autogenerate -m "add_doc_job_agent_columns"`, then verify and correct.

### 2. DocGenerationJob Model Updates

Update `DocGenerationJob` in `orch/db/models.py` with the three new columns (matching existing column patterns).

### 3. DocService Job Lifecycle Methods

Add to `DocService`:

```python
def create_doc_job(
    self,
    project_id: str,
    doc_id: str,       # This is the doc's doc_id (not composite id)
    requested_by: str = "user",
) -> DocGenerationJob
```
- Creates job with `status=queued`, generates UUID for job `id`
- Raises `KeyError` if `ProjectDoc` not found for `(project_id, doc_id)`

```python
def start_doc_job(
    self,
    job_id: str,
    pid: int | None = None,
    skill_used: str | None = None,
) -> DocGenerationJob
```
- Transitions `queued → running`, sets `started_at`, `agent_pid`, `skill_used`
- Raises `ValueError` if job not in `queued` state

```python
def complete_doc_job(
    self,
    job_id: str,
    error: str | None = None,
) -> DocGenerationJob
```
- If `error` is None: transitions `running → completed`
- If `error` provided: transitions `running → failed`, sets `error` field
- Sets `completed_at = datetime.utcnow()`, computes `duration_seconds`
- Idempotent: if job is already `completed`/`failed`, returns existing record without error

```python
def get_running_jobs_count(self, project_id: str) -> int
```
- Returns count of `DocGenerationJob` records with `status=running` for the project

```python
def get_queued_jobs(self, project_id: str, limit: int = 10) -> list[DocGenerationJob]
```
- Returns queued jobs ordered by `requested_at ASC` (FIFO)

```python
def get_stalled_jobs(self, timeout_minutes: int = 10) -> list[DocGenerationJob]
```
- Returns jobs where `status=running` and `started_at < now() - timeout_minutes`

### 4. DocJobPoller Daemon Component

Create `orch/daemon/doc_job_poller.py`:

```python
class DocJobPoller:
    """
    Polls for queued DocGenerationJob records and launches AI agents.
    Runs as part of the main daemon poll loop.
    """
    MAX_CONCURRENT_JOBS_PER_PROJECT = 2

    def __init__(self, session_factory, config) -> None: ...

    def poll(self) -> None:
        """
        Single poll cycle:
        1. Detect and mark stalled jobs (timeout)
        2. For each project: if running_count < MAX_CONCURRENT, dequeue and launch next job
        """

    def _launch_job(self, job: DocGenerationJob, doc: ProjectDoc, project: Project) -> None:
        """
        Selects skill based on editorial_category, builds agent command,
        launches subprocess, updates job with PID.
        """

    def _select_skill(self, editorial_category: EditorialCategory) -> str:
        """
        technical | architecture | api → "iw-doc-generator"
        guide | compliance | marketing | release → "iw-doc-system"
        default → "iw-doc-generator"
        """

    def _build_agent_command(
        self,
        job: DocGenerationJob,
        doc: ProjectDoc,
        project: Project,
        skill: str,
    ) -> list[str]:
        """
        Builds the claude-code/opencode command following the project's executor pattern.
        Read executor/CLAUDE.md for the exact command format.
        The command must:
        - Pass the skill name
        - Pass source_paths as context
        - Configure on-success: iw doc-update + iw doc-job-done
        - Configure on-error: iw doc-job-done --error
        """
```

**CRITICAL**: Read `executor/CLAUDE.md` before implementing `_build_agent_command`. Mirror the exact agent launch pattern already in use. Do not invent a new pattern.

### 5. Wire DocJobPoller into Daemon

In the main daemon poll loop (read `orch/daemon/` to find where other pollers are called), add a call to `DocJobPoller.poll()` after the existing batch polling logic. Do not break existing daemon behavior.

### 6. Stall Detection

In `DocJobPoller.poll()`, before launching new jobs, call `DocService.get_stalled_jobs()` and for each stalled job, call `DocService.complete_doc_job(job_id, error="generation timeout after 10 minutes")`.

## Project Conventions

- Read existing daemon files before writing any code
- Match the session management pattern of the existing daemon (does it use a context manager? a shared session? per-poll session?)
- Match subprocess launch patterns from the executor
- No hardcoded timeouts — read from `config` object

## TDD Requirement

Write tests in `tests/unit/test_doc_job_poller.py`:
- `test_poll_launches_job_when_slot_available` — mock subprocess; assert job transitions to running
- `test_poll_respects_concurrent_limit` — 2 running jobs → no new launch
- `test_poll_marks_stalled_jobs_failed` — job started 11 minutes ago → marked failed
- `test_select_skill_technical` — assert returns "iw-doc-generator"
- `test_select_skill_guide` — assert returns "iw-doc-system"
- `test_complete_doc_job_idempotent` — calling twice on completed job → no error

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all tests pass
2. `make quality` — ruff + mypy pass

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "F-00012",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/{ts}_add_doc_job_agent_columns.py",
    "orch/doc_service.py",
    "orch/daemon/doc_job_poller.py",
    "tests/unit/test_doc_job_poller.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
