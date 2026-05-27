"""Jobs list and job detail pages — project-scoped routes."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from orch.db.models import DocGenerationJob, JobStatus, Project
from orch.jobs.aggregator import JobsAggregator, JobType
from orch.utils.log_capture import strip_ansi

if TYPE_CHECKING:
    from datetime import datetime

    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session


router = APIRouter(prefix="/project/{project_id}")


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project: Project | None = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")
    return project


def _resolve_doc_job_log_path(
    db: Session, project_id: str, job_id: str
) -> tuple[DocGenerationJob, Path]:
    """Look up the job (must belong to project_id), resolve the log path.

    ``job_id`` may be either the public ID (DOC-NNNNN) or the internal UUID.
    Raises HTTPException(404) on unknown job, missing project, or missing repo_root.

    The log path is ``Project.repo_root / "ai-dev" / "logs" / f"doc_job_{job.id}.log"``.
    Always uses ``job.id`` (the UUID) in the filename, never public_id.
    """
    project = _get_project_or_404(project_id, db)
    if project.repo_root is None:
        raise HTTPException(status_code=404, detail="Project repo_root is not configured")

    # Try lookup by public_id first (new rows), fall back to UUID PK (legacy rows)
    job: DocGenerationJob | None = db.scalar(
        select(DocGenerationJob).where(DocGenerationJob.public_id == job_id)
    )
    if job is None:
        job = db.get(DocGenerationJob, job_id)
    if job is None or job.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    log_path = Path(project.repo_root) / "ai-dev" / "logs" / f"doc_job_{job.id}.log"
    # Defence-in-depth: ensure resolved path is still inside repo_root
    repo_root_resolved = Path(project.repo_root).resolve()
    try:
        log_path_resolved = log_path.resolve()
    except OSError as exc:
        raise HTTPException(status_code=404, detail=f"Cannot resolve log path: {exc}") from exc
    if not log_path_resolved.is_relative_to(repo_root_resolved):
        raise HTTPException(status_code=404, detail="Log path resolved outside project root")

    return job, log_path


_MAX_LOG_TAIL_LINES = 200
_MAX_LOG_TAIL_LINES_HARD_CAP = 1000
_MAX_LINE_BYTES = 8 * 1024  # 8 KB per line cap
_STREAM_POLL_SECONDS = 0.25  # tight poll loop for SSE
_STREAM_HEARTBEAT_SECONDS = 15


@router.get("/jobs", response_class=HTMLResponse)
def jobs_page(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    type: list[str] = Query(default=None),  # noqa: A002
    status: list[str] = Query(default=None),
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
) -> Any:
    project = _get_project_or_404(project_id, db)

    filter_types: list[JobType] | None = None
    if type:
        filter_types = [JobType(t) for t in type]

    filter_statuses: list[str] | None = status

    parsed_date_from: datetime | None = None
    if date_from:
        try:
            import zoneinfo
            from datetime import datetime as dt

            parsed_date_from = dt.fromisoformat(date_from).replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        except ValueError:
            pass

    parsed_date_to: datetime | None = None
    if date_to:
        try:
            import zoneinfo
            from datetime import datetime as dt

            parsed_date_to = dt.fromisoformat(date_to).replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        except ValueError:
            pass

    aggregator = JobsAggregator(db)
    result = aggregator.list_jobs(
        project_id=project_id,
        types=filter_types,
        statuses=filter_statuses,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        page=page,
        page_size=25,
    )

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/jobs.html",
        {
            "current_project": project,
            "job_types": [t.value for t in JobType],
            "job_statuses": ["queued", "running", "completed", "failed", "paused", "cancelled"],
            "type_filter": type or [],
            "status_filter": status or [],
            "date_from": date_from or "",
            "date_to": date_to or "",
            "rows": result.rows,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
    )


@router.get("/jobs/fragment/table", response_class=HTMLResponse)
def jobs_fragment_table(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    type: list[str] = Query(default=None),  # noqa: A002
    status: list[str] = Query(default=None),
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
) -> Any:
    project = _get_project_or_404(project_id, db)

    filter_types: list[JobType] | None = None
    if type:
        filter_types = [JobType(t) for t in type]

    filter_statuses: list[str] | None = status

    parsed_date_from: datetime | None = None
    if date_from:
        try:
            import zoneinfo
            from datetime import datetime as dt

            parsed_date_from = dt.fromisoformat(date_from).replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        except ValueError:
            pass

    parsed_date_to: datetime | None = None
    if date_to:
        try:
            import zoneinfo
            from datetime import datetime as dt

            parsed_date_to = dt.fromisoformat(date_to).replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        except ValueError:
            pass

    aggregator = JobsAggregator(db)
    result = aggregator.list_jobs(
        project_id=project_id,
        types=filter_types,
        statuses=filter_statuses,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        page=page,
        page_size=25,
    )

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/jobs_table.html",
        {
            "current_project": project,
            "rows": result.rows,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "type_filter": type or [],
            "status_filter": status or [],
            "date_from": date_from or "",
            "date_to": date_to or "",
        },
    )


@router.get("/jobs/{job_type}/{job_id}", response_class=HTMLResponse)
def job_detail(
    project_id: str,
    job_type: str,
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)

    try:
        jt = JobType(job_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown job type: {job_type}") from None

    aggregator = JobsAggregator(db)
    job = aggregator.get_job(project_id=project_id, job_type=jt, job_id=job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    # Determine if a log file exists on disk (for conditional raw-log download link)
    log_file_exists = False
    if jt == JobType.doc_generation:
        try:
            _resolved_job, _log_path = _resolve_doc_job_log_path(db, project_id, job_id)
            log_file_exists = _log_path.is_file()
        except HTTPException:
            log_file_exists = False
    else:
        log_file_exists = False

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/job_detail.html",
        {
            "current_project": _get_project_or_404(project_id, db),
            "job": job,
            "raw": job.raw,
            "log_file_exists": log_file_exists,
        },
    )


# ---------------------------------------------------------------------------
# Doc-generation job log endpoints
# ---------------------------------------------------------------------------


@router.get("/jobs/doc_generation/{job_id}/log/tail", response_class=JSONResponse)
def doc_job_log_tail(
    project_id: str,
    job_id: str,
    db: Session = Depends(get_db),
    n: int = Query(default=_MAX_LOG_TAIL_LINES, ge=1, le=_MAX_LOG_TAIL_LINES_HARD_CAP),
) -> JSONResponse:
    """Return the last ``n`` lines of the doc-job log as JSON.

    ANSI escapes are stripped server-side. Lines longer than 8 KB are truncated.
    Missing log file → 404 with body ``{"detail": "log file not found"}``.
    Empty file → 200 with ``{"lines": [], "file_size_bytes": 0, ...}``.
    """
    _job, log_path = _resolve_doc_job_log_path(db, project_id, job_id)

    if not log_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="log file not found",
        )

    try:
        raw_bytes = log_path.read_bytes()
    except OSError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"log file not found: {exc}",
        ) from exc

    file_size_bytes = len(raw_bytes)

    try:
        raw_text = raw_bytes.decode("utf-8", errors="replace")
    except OSError:
        raw_text = ""

    text = strip_ansi(raw_text)

    # Split and take last n lines
    all_lines = text.splitlines()
    tail_lines = all_lines[-n:] if len(all_lines) > n else all_lines

    # Cap each line at 8 KB
    capped_lines: list[str] = []
    truncated_from_bytes: int | None = None
    for line in tail_lines:
        line_bytes = line.encode("utf-8")
        if len(line_bytes) > _MAX_LINE_BYTES:
            truncated_from_bytes = len(line_bytes) - _MAX_LINE_BYTES
            capped_lines.append(
                line_bytes[:_MAX_LINE_BYTES].decode("utf-8", errors="replace") + "…"
            )
        else:
            capped_lines.append(line)

    return JSONResponse(
        {
            "lines": capped_lines,
            "truncated_from_bytes": truncated_from_bytes,
            "file_size_bytes": file_size_bytes,
            "line_count": len(capped_lines),
        }
    )


async def _doc_job_log_stream(
    project_id: str,
    job_id: str,
    request: Request,
) -> Any:
    """Async generator that follows the doc-job log file as new lines are written.

    - Initial chunk: last 50 lines so a late-joiner sees recent context.
    - Follows new bytes with a tight ``asyncio.sleep(0.25)`` poll loop.
    - ``event:ping`` heartbeat every 15 seconds when no new data.
    - ``event:status data:terminal`` and close when job reaches terminal state.
    - Uses fresh SessionLocal() per status check (~every 2 seconds).
    - Breaks out of the loop if the client disconnects (``request.is_disconnected()``).
    """
    from orch.db.session import SessionLocal

    # Resolve job once outside the loop
    db = SessionLocal()
    try:
        job, log_path = _resolve_doc_job_log_path(db, project_id, job_id)
    except HTTPException:
        yield "event: error\ndata: {'error': 'job not found'}\n\n"
        return
    finally:
        db.close()

    with log_path.open("rb") as f:
        # Seek to end; read last 50 lines for context
        try:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            read_start = max(0, file_size - 4096)
            f.seek(read_start)
            initial_bytes = f.read()
            f.seek(file_size)
        except OSError:
            initial_bytes = b""

        initial_text = strip_ansi(initial_bytes.decode("utf-8", errors="replace"))
        initial_lines = initial_text.splitlines()[-50:]
        for line in initial_lines:
            line_bytes = line.encode("utf-8")
            if len(line_bytes) > _MAX_LINE_BYTES:
                line = line_bytes[:_MAX_LINE_BYTES].decode("utf-8", errors="replace") + "…"
            yield f"data: {line}\n\n"

        last_heartbeat = time.monotonic()
        last_status_check = 0.0

        while True:
            if await request.is_disconnected():
                return

            elapsed = time.monotonic() - last_heartbeat

            # Re-check job status every 2 seconds
            if time.monotonic() - last_status_check >= 2.0:
                last_status_check = time.monotonic()
                session = SessionLocal()
                try:
                    refreshed_job = session.get(DocGenerationJob, job.id)
                    if refreshed_job is None:
                        yield "event: status\ndata: terminal\n\n"
                        return
                    if refreshed_job.status in (JobStatus.completed, JobStatus.failed):
                        yield "event: status\ndata: terminal\n\n"
                        return
                finally:
                    session.close()

            # Heartbeat every 15 seconds when no new data
            if elapsed >= _STREAM_HEARTBEAT_SECONDS:
                yield "event: ping\ndata: \n\n"
                last_heartbeat = time.monotonic()

            # Read new bytes
            try:
                new_bytes = os.read(f.fileno(), 4096)
                if not new_bytes:
                    await asyncio.sleep(_STREAM_POLL_SECONDS)
                    continue
                last_heartbeat = time.monotonic()
                decoded = new_bytes.decode("utf-8", errors="replace")
                clean = strip_ansi(decoded)
                for raw_line in clean.splitlines():
                    line_bytes = raw_line.encode("utf-8")
                    if len(line_bytes) > _MAX_LINE_BYTES:
                        raw_line = (
                            line_bytes[:_MAX_LINE_BYTES].decode("utf-8", errors="replace") + "…"
                        )
                    yield f"data: {raw_line}\n\n"
            except OSError:
                await asyncio.sleep(_STREAM_POLL_SECONDS)


@router.get("/jobs/doc_generation/{job_id}/log/stream")
async def doc_job_log_stream(
    project_id: str,
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """SSE stream of the doc-job log as it is written.

    Emits one ``data:<line>\\n\\n`` per log line. Periodic ``event:ping\\ndata:\\n\\n``
    heartbeat every 15 seconds when no new data. Closes when the job reaches
    a terminal state (``completed`` or ``failed``).

    A missing log file returns an ``event:error`` frame immediately.
    """
    # Validate project and job existence before streaming — propagates 404
    _job, _log_path = _resolve_doc_job_log_path(db, project_id, job_id)
    return StreamingResponse(
        _doc_job_log_stream(project_id, job_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/jobs/doc_generation/{job_id}/log/raw")
def doc_job_log_raw(
    project_id: str,
    job_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream the raw (ANSI-encoded) log file as ``text/plain``.

    ANSI is **not** stripped — operators want the original. Log file missing → 404.
    Uses ``Content-Disposition: attachment; filename="doc_job_<job.id>.log"``.
    """
    _job, log_path = _resolve_doc_job_log_path(db, project_id, job_id)

    if not log_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="log file not found",
        )

    def iterfile() -> Any:
        with log_path.open("rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="doc_job_{_job.id}.log"',
        },
    )
