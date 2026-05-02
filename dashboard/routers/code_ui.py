"""Code Understanding dashboard router — project-level Code tab and index job UI."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.utils.markdown import render_markdown
from orch.config import load_config
from orch.db.models import CodeIndexJob, DocIndexJob, Project
from orch.doc_service import DocService
from orch.rag.config import build_code_config_from_project
from orch.rag.job import JOB_REGISTRY, JobAlreadyRunningError, start_index_job
from orch.rag.mapgen import strip_trailing_arch_diagram_section

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session


router = APIRouter(prefix="/project/{project_id}")


def _clean_diagram_dsl(raw: str) -> str:
    """Strip HTML comments and YAML frontmatter from a stored diagram DSL.

    Stored docs may contain a '<!-- purpose: ... -->' comment prefix and/or
    a '---\\nconfig:\\n  layout: elk\\n---' frontmatter block. Both must be
    removed before the DSL is handed to the Mermaid renderer.
    """
    dsl = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL).strip()
    if dsl.startswith("---"):
        end = dsl.find("\n---", 3)
        if end != -1:
            dsl = dsl[end + 4 :].lstrip()
    return dsl


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
    return pattern.sub(r'<pre data-lang="mermaid"><code>\1</code></pre>', text)


def _render_architecture_html(arch_doc: Any) -> str | None:
    if arch_doc is None or not arch_doc.content:
        return None
    cleaned = strip_trailing_arch_diagram_section(arch_doc.content)
    processed = _preprocess_mermaid(cleaned)
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
            "level1_doc_id": arch_doc.id if arch_doc else None,
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
    arch_diagram_dsl: str | None = None
    arch_purpose: str | None = None
    if last_completed_job and last_completed_job.doc_id:
        arch_doc_for_template = DocService(db).get_doc(project_id, "architecture-map")
        if arch_doc_for_template:
            content_html = _render_architecture_html(arch_doc_for_template)
        arch_diagram_doc = DocService(db).get_doc(project_id, "diagram-architecture")
        if arch_diagram_doc and arch_diagram_doc.content:
            m = re.search(r"<!-- purpose: (.*?) -->", arch_diagram_doc.content)
            if m:
                arch_purpose = m.group(1).strip()
            arch_diagram_dsl = _clean_diagram_dsl(arch_diagram_doc.content)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "project_code.html",
        {
            "current_project": project,
            "project_id": project_id,
            "index_status": index_status,
            "running_job": running_job,
            "last_completed_job": last_completed_job,
            "last_completed_recent": last_completed_recent,
            "last_completed_duration": last_completed_duration,
            "arch_doc": arch_doc_for_template,
            "content_html": content_html,
            "arch_diagram_dsl": arch_diagram_dsl,
            "arch_purpose": arch_purpose,
        },
    )


def _latest_job(db: Session, project_id: str, status: str) -> CodeIndexJob | None:
    order_col = (
        CodeIndexJob.completed_at.desc()
        if status in ("completed", "failed", "cancelled")
        else CodeIndexJob.triggered_at.desc()
    )
    return db.scalar(
        select(CodeIndexJob)
        .where(
            CodeIndexJob.project_id == project_id,
            CodeIndexJob.status == status,
        )
        .order_by(order_col)
        .limit(1)
    )


def _last_error(job: CodeIndexJob | None) -> str | None:
    if job is None or not job.errors:
        return None
    errors = list(job.errors)
    return str(errors[-1]) if errors else None


@router.get("/api/code/status", response_class=HTMLResponse)
def code_status(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)

    running_job = _latest_job(db, project_id, "running")
    last_completed_job = _latest_job(db, project_id, "completed")
    last_failed_job = _latest_job(db, project_id, "failed")

    templates: Jinja2Templates = request.app.state.templates

    if running_job:
        return templates.TemplateResponse(
            request,
            "fragments/code_job_status.html",
            {"running_job": running_job, "project_id": project_id},
        )

    # Show the failed banner only when the most recent terminal job failed.
    # If a later completed job exists, the failure is stale.
    failed_is_latest = last_failed_job is not None and (
        last_completed_job is None
        or (last_completed_job.completed_at or datetime.min.replace(tzinfo=UTC))
        < (last_failed_job.completed_at or datetime.min.replace(tzinfo=UTC))
    )
    if failed_is_latest:
        return templates.TemplateResponse(
            request,
            "fragments/code_job_failed.html",
            {
                "last_failed_job": last_failed_job,
                "last_failed_error": _last_error(last_failed_job),
                "project_id": project_id,
            },
        )

    if last_completed_job:
        return templates.TemplateResponse(
            request,
            "fragments/code_job_report.html",
            {
                "last_completed_job": last_completed_job,
                "last_completed_duration": _format_duration(last_completed_job),
                "current_project": _get_project_or_404(project_id, db),
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
    arch_diagram_doc = svc.get_doc(project_id, "diagram-architecture")
    arch_diagram_dsl = None

    if arch_doc is None:
        templates: Jinja2Templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "fragments/code_empty_state.html",
            {"project_id": project_id},
        )

    content_html = _render_architecture_html(arch_doc)
    arch_purpose = None
    if arch_diagram_doc and arch_diagram_doc.content:
        m = re.search(r"<!-- purpose: (.*?) -->", arch_diagram_doc.content)
        if m:
            arch_purpose = m.group(1).strip()
        arch_diagram_dsl = _clean_diagram_dsl(arch_diagram_doc.content)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/code_architecture_view.html",
        {
            "current_project": _get_project_or_404(project_id, db),
            "content_html": content_html,
            "arch_doc": arch_doc,
            "arch_diagram_dsl": arch_diagram_dsl,
            "arch_purpose": arch_purpose,
        },
    )


@router.get("/api/code/index/stream")
async def code_index_stream(
    project_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    runner = JOB_REGISTRY.get(project_id)

    if runner is None:
        # The job may have finished (including failing) before the browser
        # opened this stream. Surface a terminal status from the DB so the UI
        # doesn't idle-spin forever after a fast failure.
        recent_cutoff = datetime.now(UTC) - timedelta(minutes=5)
        recent_job: CodeIndexJob | None = db.scalar(
            select(CodeIndexJob)
            .where(
                CodeIndexJob.project_id == project_id,
                CodeIndexJob.completed_at.is_not(None),
                CodeIndexJob.completed_at >= recent_cutoff,
            )
            .order_by(CodeIndexJob.completed_at.desc())
            .limit(1)
        )
        if recent_job is not None and recent_job.status == "failed":
            err = _last_error(recent_job) or "unknown error"
            failed_payload = json.dumps(
                {
                    "event": "done",
                    "status": "failed",
                    "error": err,
                    "job_id": recent_job.id,
                }
            )

            async def failed_generator() -> AsyncGenerator[str, None]:
                yield f"data: {failed_payload}\n\n"

            return StreamingResponse(
                failed_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

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

    cfg = load_config()
    code_cfg = build_code_config_from_project(project.config, cfg.index_path)

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
        f'<div hx-get="/project/{project_id}/api/code/status" '
        f'hx-trigger="load" hx-target="this" hx-swap="outerHTML"></div>',
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


@router.post("/api/code/reindex-docs", response_class=HTMLResponse)
def reindex_docs(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)

    stale_threshold = datetime.now(UTC) - timedelta(minutes=5)
    running = db.scalar(
        select(DocIndexJob)
        .where(
            DocIndexJob.project_id == project_id,
            DocIndexJob.status.in_(("queued", "running")),
            DocIndexJob.triggered_at >= stale_threshold,
        )
        .limit(1)
    )
    if running:
        templates: Jinja2Templates = request.app.state.templates
        fragment = templates.TemplateResponse(
            request,
            "fragments/doc_job_already_running.html",
            {
                "project_id": project_id,
                "job_id": running.id,
            },
        )
        fb = fragment.body
        body_bytes = bytes(fb) if isinstance(fb, memoryview) else fb
        return HTMLResponse(
            content=body_bytes.decode("utf-8"),
            status_code=409,
            headers={"HX-Trigger": '{"docJobConflict": {}}'},
        )

    project = _get_project_or_404(project_id, db)
    cfg = load_config()
    code_cfg = build_code_config_from_project(project.config, cfg.index_path)

    job = DocIndexJob(
        id=str(uuid.uuid4()),
        project_id=project_id,
        status="queued",
        provider="local",
        llm_model=code_cfg.resolved_llm_model(),
        embed_model=code_cfg.resolved_embed_model(),
        index_tier=code_cfg.index_tier.value,
    )
    db.add(job)
    db.commit()

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/code_job_status.html",
        {
            "running_job": job,
            "project_id": project_id,
            "job_type_label": "Doc indexing",
        },
    )


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
