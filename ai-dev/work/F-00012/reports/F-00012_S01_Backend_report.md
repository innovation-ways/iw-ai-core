# F-00012 S01 Backend Report

## What Was Done

Implemented the daemon backend for F-00012 (AI Documentation Generation Phase 2):

1. **Alembic Migration** (`73a7ae48b82b_add_doc_job_agent_columns.py`): Added three columns to `doc_generation_jobs` table:
   - `agent_pid` (Integer, nullable)
   - `skill_used` (String(100), nullable)
   - `duration_seconds` (Integer, nullable)

2. **DocGenerationJob Model** (`orch/db/models.py`): Added the three new columns to the model.

3. **DocService Job Lifecycle Methods** (`orch/doc_service.py`): Added 6 new methods:
   - `create_doc_job()`: Creates job with `status=queued`
   - `start_doc_job()`: Transitions `queued → running`, sets `started_at`, `agent_pid`, `skill_used`
   - `complete_doc_job()`: Transitions to `completed` or `failed`, computes `duration_seconds`, idempotent
   - `get_running_jobs_count()`: Count of running jobs per project
   - `get_queued_jobs()`: FIFO queued jobs ordered by `requested_at`
   - `get_stalled_jobs()`: Jobs running >10 minutes (configurable)

4. **DocJobPoller** (`orch/daemon/doc_job_poller.py`): New daemon component that:
   - Detects and marks stalled jobs (timeout after 10 minutes)
   - Enqueues new jobs respecting `MAX_CONCURRENT_JOBS_PER_PROJECT = 2` per project
   - Launches agents via `subprocess.Popen` with skill-based routing
   - Skill mapping: `technical|functional → iw-doc-generator`, `guide|compliance|marketing|release → iw-doc-system`

5. **Wired into Daemon** (`orch/daemon/main.py`): Added `DocJobPoller` to the poll cycle (Phase 3 after batch processing).

6. **Unit Tests** (`tests/unit/test_doc_job_poller.py`): 15 tests covering skill selection, job lifecycle, and poller launch behavior. All 594 tests pass.

## Files Changed

- `orch/db/models.py` — added `agent_pid`, `skill_used`, `duration_seconds` to `DocGenerationJob`
- `orch/db/migrations/versions/73a7ae48b82b_add_doc_job_agent_columns.py` — migration
- `orch/doc_service.py` — added 6 job lifecycle methods
- `orch/daemon/doc_job_poller.py` — new `DocJobPoller` class
- `orch/daemon/main.py` — wired `DocJobPoller.poll()` into poll cycle
- `tests/unit/test_doc_job_poller.py` — 15 unit tests

## Test Results

```
======================== 594 passed, 1 warning in 1.19s ========================
make quality: All checks passed (ruff + format + mypy)
```

## Issues/Observations

- The `_EXECUTOR_DIR` constant in `doc_job_poller.py` is defined but not used — it was included for consistency but the actual agent launch uses `subprocess.Popen` directly in `_launch_job` rather than calling executor scripts. This is intentional since doc jobs don't use worktrees.
- `requested_by` parameter in `create_doc_job` is accepted but stored in `requested_at` only (timestamp-based audit). The parameter is present for API completeness but not stored — flagged with `noqa: ARG002`.
- Migration used `sa.String(100)` instead of `sa.Text(100)` to avoid PostgreSQL syntax error on `TEXT(100)` type modifier.