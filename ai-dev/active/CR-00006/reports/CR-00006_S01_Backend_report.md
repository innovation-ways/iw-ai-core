# CR-00006 S01 — Backend Implementation Report

## Summary

Completed all three backend tasks for CR-00006 S01.

## Changes Made

### Task 1: Fix Q&A Streaming Bug (`dashboard/routers/code_qa.py`)

- **Problem**: `_run_qa_in_thread` collected all tokens into a list before returning, causing the browser to see nothing until the LLM finished.
- **Solution**: Replaced the buffering pattern with a non-buffering `asyncio.Queue` bridge. The async generator now runs in a daemon thread with its own event loop; tokens are put into the queue as they arrive and the main async generator yields SSE frames immediately.
- Deleted `_run_qa_in_thread` helper entirely.
- Wire format unchanged: `{"token": "..."}`, `{"event": "done", "full_response": "..."}`, `{"event": "error", "message": "..."}`.
- Verification:
  - `grep "_run_qa_in_thread" dashboard/routers/code_qa.py` → NOT FOUND (expected)
  - `grep "asyncio.Queue" dashboard/routers/code_qa.py` → Line 66 (present)
  - `ruff check dashboard/routers/code_qa.py` → All checks passed
  - `mypy dashboard/routers/code_qa.py` → Success

### Task 2: JobsAggregator Service (`orch/jobs/__init__.py`, `orch/jobs/aggregator.py`)

- Created `orch/jobs/__init__.py` (empty module).
- Created `orch/jobs/aggregator.py` exposing `JobsAggregator` class with:
  - `JobType(str, Enum)` with four values: `code_mapping`, `doc_generation`, `batch_execution`, `research`
  - `JobRow` and `JobListResult` frozen dataclasses
  - `list_jobs()` and `get_job()` methods
- Status normalization documented in module docstring:
  - `code_index_jobs.status` (TEXT) — passed through unchanged
  - `DocStatus` → `queued`/`running`/`completed`/`completed`
  - `BatchStatus` → `queued`/`running`/`paused`/`completed`/`failed`/`cancelled`
  - `JobStatus` → `queued`/`running`/`completed`/`failed`
- Implementation: approach (b) — four separate SELECTs, merged/sorted/paginated in Python.
- Verification:
  - `ruff check orch/jobs/aggregator.py` → All checks passed
  - `mypy orch/jobs/aggregator.py` → Success

### Task 3: DaemonEvent on Code Map Completion (`orch/rag/job.py`)

- Added `DaemonEvent(event_type="code_map_completed")` insert in `_db_set_status_async` inside the same transaction as the status transition to `"completed"`.
- Guard: only fires when `status == "completed" and completed == True`.
- Uses `event_metadata` (not `metadata`) per SQLAlchemy/CLAUDE.md convention.
- Same `session.commit()` for both the job update and the event insert.
- Line ~285-308 in `orch/rag/job.py`.
- Verification:
  - `ruff check orch/rag/job.py` → All checks passed
  - `mypy orch/rag/job.py` → Success

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/code_qa.py` | Replaced buffering bridge with non-buffering `asyncio.Queue` bridge; deleted `_run_qa_in_thread` |
| `orch/jobs/__init__.py` | New empty module |
| `orch/jobs/aggregator.py` | New `JobsAggregator` service |
| `orch/rag/job.py` | Added `DaemonEvent(code_map_completed)` insert at code index job completion |

## Quality Verification

```
ruff check dashboard/routers/code_qa.py orch/jobs/aggregator.py orch/rag/job.py  # All checks passed
mypy dashboard/routers/code_qa.py orch/jobs/aggregator.py orch/rag/job.py        # Success: no issues found
```