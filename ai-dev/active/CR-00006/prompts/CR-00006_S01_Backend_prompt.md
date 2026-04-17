# CR-00006 S01 — Backend Implementation

## Input Files (read before changing anything)

- `CLAUDE.md` and `orch/CLAUDE.md` — hard rules and architecture
- `ai-dev/active/CR-00006/CR-00006_CR_Design.md` — full design (source of truth for this work)
- `dashboard/routers/code_qa.py` — the file containing the streaming bug
- `orch/rag/qa.py` — `QAEngine.answer_stream()` (do NOT modify — read only)
- `orch/db/models.py` lines 572-688 (Batch, BatchItem), 716-753 (DaemonEvent), 816-885 (ProjectDoc), 912-968 (DocGenerationJob), 1041-1117 (CodeIndexJob)
- `orch/rag/job.py` — locate the code index completion path (where `CodeIndexJob.status = "completed"` is set) — this is where the new `DaemonEvent` insert goes
- `dashboard/routers/sse.py:22-135` — toast map reference

## Output Files (created/modified)

- **Modified**: `dashboard/routers/code_qa.py` — replace buffering bridge with non-buffering bridge
- **New**: `orch/jobs/__init__.py`
- **New**: `orch/jobs/aggregator.py` — read-only service that unions the four job sources
- **Modified**: `orch/rag/job.py` (or whichever module finalizes `CodeIndexJob`) — insert `DaemonEvent(event_type="code_map_completed")` in the same transaction as status transition to `completed`

## Context

**Work item**: CR-00006
**Step**: S01
**Agent**: backend-impl

This CR has three user-visible changes. S01 owns the non-UI backend changes:

1. Fix the Q&A streaming bug so tokens reach the browser as Ollama emits them.
2. Build a read-only `JobsAggregator` service that unions four existing tables (no schema change).
3. Insert a `DaemonEvent` on code map completion so the existing SSE toast system can surface it (replaces the green banner).

## Task 1: Fix the Q&A streaming bridge

### The bug

`dashboard/routers/code_qa.py:60-82` (`_run_qa_in_thread`) runs the async generator **to completion** inside a thread, collecting every token into a list, then returns the list. The outer `_sse_generator` at lines 85-124 awaits that list, then iterates it and yields SSE frames. Result: the client sees nothing until the LLM finishes.

### The fix

Rewrite the streaming internals without changing the endpoint signature or wire format. Recommended approach:

```python
import asyncio
import json
import threading
from typing import TYPE_CHECKING

_SENTINEL_DONE = object()  # module-level singletons (can also be strings)
_SENTINEL_ERROR = object()


async def _sse_generator(
    project_id: str,
    question: str,
    context_level: str,
    context_doc_id: str | None,
    module_path: str | None,
    conversation_history: list[dict[str, str]],
    db_session: Session,
    config: CodeUnderstandingConfig,
) -> AsyncGenerator[str, None]:
    """Yield SSE frames as tokens are produced — no buffering."""
    from orch.rag.qa import QAEngine

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    stop_event = threading.Event()

    def _worker() -> None:
        # Run the async generator inside this thread's own event loop.
        async def _drain() -> None:
            engine = QAEngine(project_id=project_id, config=config)
            try:
                async for token in engine.answer_stream(
                    question=question,
                    context_level=context_level,
                    context_doc_id=context_doc_id,
                    module_path=module_path,
                    conversation_history=conversation_history,
                    session=db_session,  # type: ignore[arg-type]
                ):
                    if stop_event.is_set():
                        return
                    loop.call_soon_threadsafe(queue.put_nowait, ("token", token))
            except (ConnectionRefusedError, OSError) as exc:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    ("error", "Local AI unavailable. Check that Ollama is running."),
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

        asyncio.run(_drain())

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    full_response_parts: list[str] = []
    try:
        while True:
            kind, payload = await queue.get()
            if kind == "error":
                yield f'data: {json.dumps({"event": "error", "message": payload})}\n\n'
                return
            if kind == "done":
                yield f'data: {json.dumps({"event": "done", "full_response": "".join(full_response_parts)})}\n\n'
                return
            # kind == "token"
            # Filter out the legacy "__ERROR__:" prefix QAEngine sometimes yields.
            if isinstance(payload, str) and payload.startswith("__ERROR__:"):
                yield f'data: {json.dumps({"event": "error", "message": payload[len("__ERROR__:") :]})}\n\n'
                return
            full_response_parts.append(payload)
            yield f'data: {json.dumps({"token": payload})}\n\n'
    finally:
        stop_event.set()
```

Notes:
- Keep the wire format identical: `{"token": "..."}`, `{"event": "done", "full_response": "..."}`, `{"event": "error", "message": "..."}`.
- Do **not** call `asyncio.run(...)` on the main request loop — use the worker thread's own loop.
- Delete the now-unused `_run_qa_in_thread` helper.
- The endpoint function (`code_qa`) keeps the same signature and `StreamingResponse` headers.
- Preserve the existing index-path 404 check (lines 144-149).

### Verification inside the file

After editing, confirm:
- `grep -n "_run_qa_in_thread" dashboard/routers/code_qa.py` — no matches (helper deleted).
- `grep -n "asyncio.Queue" dashboard/routers/code_qa.py` — at least one match.
- `ruff check dashboard/routers/code_qa.py` — clean.
- `mypy dashboard/routers/code_qa.py` — clean (you may need `# type: ignore[misc]` on the `queue.get()` unpacking if mypy complains).

## Task 2: Build the JobsAggregator service

### Files

Create:

- `orch/jobs/__init__.py` — empty module
- `orch/jobs/aggregator.py` — the service

### Specification

A `JobsAggregator` exposes:

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal


class JobType(str, Enum):
    code_mapping = "code_mapping"
    doc_generation = "doc_generation"
    batch_execution = "batch_execution"
    research = "research"


@dataclass(frozen=True)
class JobRow:
    job_type: JobType
    job_id: str            # native PK of source row (code_index_jobs.id, doc_generation_jobs.id, batches.id, project_docs.id)
    project_id: str
    title: str             # human label ("Code map — full", doc title, batch name, research title)
    status: str            # lower-case status string, normalised: queued|running|completed|failed|cancelled
    started_at: datetime | None
    finished_at: datetime | None
    triggered_by: str | None   # best-effort (skill_used, trigger_reason, or None)
    raw: dict               # full source-row dict for the detail page


@dataclass(frozen=True)
class JobListResult:
    rows: list[JobRow]
    total: int              # count before pagination
    page: int
    page_size: int


class JobsAggregator:
    def __init__(self, session: Session) -> None: ...

    def list_jobs(
        self,
        *,
        project_id: str,
        types: list[JobType] | None = None,
        statuses: list[str] | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: Literal["started_at", "finished_at", "status", "job_type"] = "started_at",
        sort_dir: Literal["asc", "desc"] = "desc",
    ) -> JobListResult: ...

    def get_job(
        self,
        *,
        project_id: str,
        job_type: JobType,
        job_id: str,
    ) -> JobRow | None: ...
```

### Source-table mapping

| JobType | Table | `started_at` source | `finished_at` source | `status` source | `title` source | `triggered_by` source |
|---------|-------|---------------------|----------------------|-----------------|----------------|-----------------------|
| code_mapping | `code_index_jobs` | `triggered_at` | `completed_at` | `status` (TEXT — already lowercase) | `"Code map — " + COALESCE(index_tier, "default")` | NULL (no user column) |
| doc_generation | `doc_generation_jobs` | `started_at` (fallback `requested_at`, then `created_at`) | `completed_at` | `status` (JobStatus enum value) | `ProjectDoc.title` via `doc_id` join; fallback `"Doc generation (orphan)"` | `skill_used` (fallback `trigger_reason`) |
| batch_execution | `batches` | `created_at` | `completed_at` | `status` (BatchStatus enum value) | `"Batch " + id` | NULL |
| research | `project_docs` WHERE `doc_type = 'research'` | `created_at` | `generated_at` (if status == published else NULL) | `status` (DocStatus enum value) | `title` | `generated_by` |

### Implementation approach

Two reasonable options:
- **(a)** SQL `UNION ALL` across all four tables with a computed `job_type` column, pagination applied on the union. Cleanest performance but trickier SQL with enum casts.
- **(b)** Python-side aggregation: run one SELECT per source with the same filters/ordering, merge, sort, paginate. Simpler and adequate at current scale.

**Use approach (b)** — four separate SELECTs, merge in Python, sort and paginate in Python. Each SELECT uses filters efficiently (LIMIT pushed down where possible: apply date filters + per-source `LIMIT page*page_size` as a cap, then merge + sort + slice).

Status normalisation: map enum values to lowercase strings. For `CodeIndexJob.status` (already TEXT), pass through. For `DocStatus` (planned, draft, published, archived) — map `published` → `completed`, `archived` → `completed`, `planned` → `queued`, `draft` → `running`. For `BatchStatus` — `planning` → `queued`, `approved` → `queued`, `executing` → `running`, `completed`/`failed` pass through, others → lowercase name. Document this mapping in a module docstring.

### Tests expected later (S07)

S01 does **not** write tests. S07 will add `tests/unit/test_jobs_aggregator.py` that seeds all four tables and asserts correct behaviour. Make sure the aggregator is trivially testable: accept a session, no global state, no side effects.

## Task 3: Emit DaemonEvent on code map completion

### Where

Find the place where a code index job is marked completed. Based on design analysis, this is in `orch/rag/job.py` in a `CodeIndexJobRunner` class or a helper it calls. It sets `CodeIndexJob.status = "completed"` and `completed_at = datetime.now(UTC)`.

### What to add

In the same DB transaction/commit as the status transition:

```python
from orch.db.models import DaemonEvent

db.add(DaemonEvent(
    project_id=job.project_id,
    event_type="code_map_completed",
    entity_id=job.id,
    message=f"Code map generated — {job.files_indexed} files, {job.chunks_created} chunks",
    event_metadata={
        "job_id": job.id,
        "llm_model": job.llm_model,
        "embed_model": job.embed_model,
        "index_tier": job.index_tier,
        "files_indexed": job.files_indexed,
        "chunks_created": job.chunks_created,
        "duration_seconds": (
            int((job.completed_at - job.triggered_at).total_seconds())
            if job.completed_at and job.triggered_at else None
        ),
    },
))
```

**Important**:
- Use the Python attribute `event_metadata` (SQLAlchemy reserves `metadata` — see `CLAUDE.md` critical rules).
- The insert must be in the same `db.commit()` as the status update — if the commit fails, the event must not be persisted.
- Do **not** add the event if `job.status` is being set to `failed` or `cancelled` — only on successful completion.

### Don't do here

- Do **not** modify `sse.py` in this step (S03 will add `code_map_completed` to the toast map). The event row will be ignored by the current SSE filter until S03 lands.

## Signal completion

```bash
iw step-done CR-00006 S01 --summary "Replaced buffering Q&A bridge with non-buffering asyncio.Queue bridge in dashboard/routers/code_qa.py; added orch/jobs/aggregator.py (read-only union of code_index_jobs + doc_generation_jobs + batches + research project_docs); inserted DaemonEvent(code_map_completed) at code index job completion path"
```

If anything blocks you (e.g., the code completion path is not in `orch/rag/job.py`):

```bash
iw step-fail CR-00006 S01 --reason "<what failed — include exact file/line you expected to find and what you found instead>"
```
