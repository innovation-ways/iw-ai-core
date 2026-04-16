"""Code Understanding dashboard router — project-level Code tab and index job UI."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.utils.markdown import render_markdown
from orch.db.models import CodeIndexJob, Project
from orch.doc_service import DocService
from orch.rag.config import CodeUnderstandingConfig
from orch.rag.job import JOB_REGISTRY, JobAlreadyRunningError, start_index_job

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session


router = APIRouter(prefix="/project/{project_id}")


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")
    return project


def _get_provider_label(project: Project) -> str:
    code_cfg = (project.config or {}).get("code_understanding", {})
    tier = code_cfg.get("index_tier", "balanced")
    return f"local ({tier})"


def _format_duration(job: CodeIndexJob) -> str | None:
    if job.completed_at is None or job.triggered_at is None:
        return None
    delta = job.completed_at - job.triggered_at
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes, seconds = divmod(total_seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _preprocess_mermaid(text: str) -> str:
    pattern = re.compile(r"```mermaid\s*(.*?)\s*```", re.DOTALL)
    return pattern.sub(r'<div class="mermaid">\1</div>', text)


def _render_architecture_html(arch_doc: Any) -> str | None:
    if arch_doc is None or not arch_doc.content:
        return None
    processed = _preprocess_mermaid(arch_doc.content)
    return render_markdown(processed)


@router.get("/code", response_class=HTMLResponse)
def code_page(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)

    last_completed_job: CodeIndexJob | None = db.scalar(
        select(CodeIndexJob)
        .where(
            CodeIndexJob.project_id == project_id,
            CodeIndexJob.status == "completed",
        )
        .order_by(CodeIndexJob.completed_at.desc())
        .limit(1)
    )

    running_job: CodeIndexJob | None = db.scalar(
        select(CodeIndexJob)
        .where(
            CodeIndexJob.project_id == project_id,
            CodeIndexJob.status == "running",
        )
        .limit(1)
    )

    index_status: dict[str, Any] | None = None
    if last_completed_job:
        arch_doc: Any = None
        if last_completed_job.doc_id:
            arch_doc = DocService(db).get_doc(project_id, "architecture-map")
        index_status = {
            "provider": _get_provider_label(project),
            "llm_model": last_completed_job.llm_model,
            "embed_model": last_completed_job.embed_model,
            "last_indexed_at": last_completed_job.completed_at,
            "files_count": last_completed_job.files_indexed or 0,
            "chunks_count": last_completed_job.chunks_created or 0,
            "languages_detected": last_completed_job.languages_detected or [],
            "level1_doc_markdown": arch_doc.content if arch_doc else None,
        }

    last_completed_recent = (
        last_completed_job is not None
        and last_completed_job.completed_at is not None
        and (datetime.now(UTC) - last_completed_job.completed_at) < timedelta(hours=1)
    )

    last_completed_duration = _format_duration(last_completed_job) if last_completed_job else None

    arch_doc_for_template: Any = None
    content_html: str | None = None
    if last_completed_job and last_completed_job.doc_id:
        arch_doc_for_template = DocService(db).get_doc(project_id, "architecture-map")
        if arch_doc_for_template:
            content_html = _render_architecture_html(arch_doc_for_template)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "project_code.html",
        {
            "current_project": project,
            "index_status": index_status,
            "running_job": running_job,
            "last_completed_job": last_completed_job,
            "last_completed_recent": last_completed_recent,
            "last_completed_duration": last_completed_duration,
            "arch_doc": arch_doc_for_template,
            "content_html": content_html,
        },
    )


@router.get("/api/code/status", response_class=HTMLResponse)
def code_status(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)

    last_completed_job: CodeIndexJob | None = db.scalar(
        select(CodeIndexJob)
        .where(
            CodeIndexJob.project_id == project_id,
            CodeIndexJob.status == "completed",
        )
        .order_by(CodeIndexJob.completed_at.desc())
        .limit(1)
    )

    running_job: CodeIndexJob | None = db.scalar(
        select(CodeIndexJob)
        .where(
            CodeIndexJob.project_id == project_id,
            CodeIndexJob.status == "running",
        )
        .limit(1)
    )

    templates: Jinja2Templates = request.app.state.templates

    if running_job:
        return templates.TemplateResponse(
            request,
            "fragments/code_job_status.html",
            {"running_job": running_job, "project_id": project_id},
        )

    if last_completed_job:
        return templates.TemplateResponse(
            request,
            "fragments/code_job_status.html",
            {
                "running_job": None,
                "last_completed_job": last_completed_job,
                "project_id": project_id,
            },
        )

    return templates.TemplateResponse(
        request,
        "fragments/code_empty_state.html",
        {"project_id": project_id},
    )


@router.get("/api/code/architecture", response_class=HTMLResponse)
def code_architecture(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)

    svc = DocService(db)
    arch_doc = svc.get_doc(project_id, "architecture-map")

    if arch_doc is None:
        templates: Jinja2Templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "fragments/code_empty_state.html",
            {"project_id": project_id},
        )

    content_html = _render_architecture_html(arch_doc)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/code_architecture_view.html",
        {
            "current_project": _get_project_or_404(project_id, db),
            "content_html": content_html,
            "arch_doc": arch_doc,
        },
    )


@router.get("/api/code/index/stream")
async def code_index_stream(project_id: str) -> StreamingResponse:
    runner = JOB_REGISTRY.get(project_id)

    if runner is None:

        async def idle_generator() -> AsyncGenerator[str, None]:
            yield 'data: {"event": "done", "status": "idle"}\n\n'

        return StreamingResponse(
            idle_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    queue = runner.progress_queue
    job_id = runner.job_id

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                event = await queue.get()
                if event.get("phase") == "done":
                    done_payload = json.dumps(
                        {"event": "done", "status": "completed", "job_id": job_id}
                    )
                    yield f"data: {done_payload}\n\n"
                    break
                if event.get("phase") == "error":
                    err_payload = json.dumps(
                        {
                            "event": "done",
                            "status": "failed",
                            "error": event.get("message", "unknown error"),
                        }
                    )
                    yield f"data: {err_payload}\n\n"
                    break
                if event.get("phase") == "cancelled":
                    cancel_payload = json.dumps(
                        {"event": "done", "status": "cancelled", "job_id": job_id}
                    )
                    yield f"data: {cancel_payload}\n\n"
                    break
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _trigger_job(
    db: Session,
    project_id: str,
    mode: str,
    background_tasks: BackgroundTasks,
) -> HTMLResponse:
    project = _get_project_or_404(project_id, db)

    code_cfg_dict = (project.config or {}).get("code_understanding", {})
    code_cfg = CodeUnderstandingConfig(**code_cfg_dict)

    job = CodeIndexJob(
        project_id=project_id,
        status="queued",
        llm_model=code_cfg.resolved_llm_model(),
        embed_model=code_cfg.resolved_embed_model(),
        index_tier=code_cfg.index_tier.value,
    )
    db.add(job)
    db.commit()

    try:
        runner = start_index_job(job, project, mode=mode)  # type: ignore[arg-type]
    except JobAlreadyRunningError as err:
        raise HTTPException(
            status_code=409,
            detail="A job is already running for this project",
        ) from err

    background_tasks.add_task(runner.run)

    return HTMLResponse(
        '<div hx-swap-oob="true" id="code-status-panel">Job started</div>',
        headers={"HX-Trigger": '{"codeJobStarted": {}}'},
    )


@router.post("/api/code/index", response_class=HTMLResponse)
def code_trigger_index(
    project_id: str,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Any:
    return _trigger_job(db, project_id, "full", background_tasks)


@router.post("/api/code/reindex", response_class=HTMLResponse)
def code_trigger_reindex(
    project_id: str,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Any:
    return _trigger_job(db, project_id, "incremental", background_tasks)


@router.post("/api/code/regen-map", response_class=HTMLResponse)
def code_trigger_regen_map(
    project_id: str,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Any:
    return _trigger_job(db, project_id, "mapgen_only", background_tasks)


@router.delete("/api/code/index", response_class=HTMLResponse)
def code_cancel_index(
    project_id: str,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)

    runner = JOB_REGISTRY.get(project_id)
    if runner is None:
        raise HTTPException(status_code=404, detail="No running job for this project")

    runner.request_cancel()

    return HTMLResponse(
        '<div hx-swap-oob="true" id="code-status-panel">Cancelling...</div>',
        headers={"HX-Trigger": '{"codeJobCancelled": {}}'},
    )
