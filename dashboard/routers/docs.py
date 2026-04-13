"""Docs router — project-level documentation library and detail pages."""

from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.utils.markdown import render_markdown
from orch.db.models import DocStatus, DocType, JobStatus, Project
from orch.doc_service import DocService

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


@router.get("/docs", response_class=HTMLResponse)
def docs_library(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)
    docs = svc.list_docs(project_id)
    doc_types = [dt.value for dt in DocType]
    statuses = [ds.value for ds in DocStatus]
    stale_docs = svc.get_stale_docs(project_id, project.repo_root)
    stale_doc_ids = {doc.doc_id for doc, _, _ in stale_docs}
    stale_source_map = {doc.doc_id: path for doc, path, _ in stale_docs}
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "docs_library.html",
        {
            "current_project": project,
            "docs": docs,
            "doc_types": doc_types,
            "statuses": statuses,
            "stale_doc_ids": stale_doc_ids,
            "stale_source_map": stale_source_map,
        },
    )


@router.get("/docs/{doc_id}", response_class=HTMLResponse)
def docs_detail(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    versions = svc.list_doc_versions(project_id, doc_id)
    content_html = render_markdown(doc.content) if doc.content else ""
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "docs_detail.html",
        {
            "current_project": project,
            "doc": doc,
            "versions": versions,
            "content_html": content_html,
        },
    )


@router.get("/docs/{doc_id}/pdf")
def docs_pdf(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    if doc.content is None:
        raise HTTPException(
            status_code=404,
            detail="No content to generate PDF from",
        )

    pdf_path = doc.pdf_path
    if pdf_path and Path(pdf_path).exists():
        pdf_bytes = Path(pdf_path).read_bytes()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{doc.slug}-v{doc.version}.pdf"'
            },
        )

    templates: Jinja2Templates = request.app.state.templates
    pdf_template = templates.get_template("pdf/doc_pdf.html")
    html_content = pdf_template.render(
        doc=doc,
        project=project,
        rendered_content=render_markdown(doc.content),
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
    )

    try:
        from weasyprint import HTML  # type: ignore

        def generate_pdf() -> bytes:
            return HTML(string=html_content).write_pdf()  # type: ignore[no-any-return]

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(generate_pdf)
            try:
                pdf_bytes = future.result(timeout=10)
            except concurrent.futures.TimeoutError:
                return JSONResponse(
                    {"error": "PDF generation timed out", "retry": True},
                    status_code=504,
                )
    except ImportError:
        return JSONResponse(
            {
                "error": "PDF generation not available",
                "detail": "WeasyPrint is not installed. Run: pip install weasyprint",
            },
            status_code=501,
        )

    cache_dir = Path(project.repo_root) / "docs" / ".generated" / project_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{doc_id}-v{doc.version}.pdf"
    cache_file.write_bytes(pdf_bytes)
    svc.update_doc(project_id, doc_id, pdf_path=str(cache_file))

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{doc.slug}-v{doc.version}.pdf"'},
    )


@router.get("/api/docs/search", response_class=HTMLResponse)
def docs_search(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    q: str | None = None,
    doc_type: str | None = None,
    status: str | None = None,
) -> Any:
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)

    doc_type_enum: DocType | None = None
    if doc_type:
        for dt in DocType:
            if dt.value == doc_type:
                doc_type_enum = dt
                break

    status_enum: DocStatus | None = None
    if status:
        for ds in DocStatus:
            if ds.value == status:
                status_enum = ds
                break

    docs = svc.list_docs(
        project_id,
        doc_type=doc_type_enum,
        status=status_enum,
        search=q,
    )
    stale_docs = svc.get_stale_docs(project_id, project.repo_root)
    stale_doc_ids = {doc.doc_id for doc, _, _ in stale_docs}
    stale_source_map = {doc.doc_id: path for doc, path, _ in stale_docs}
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_search_results.html",
        {
            "docs": docs,
            "current_project_id": project_id,
            "stale_doc_ids": stale_doc_ids,
            "stale_source_map": stale_source_map,
        },
    )


@router.get("/api/docs/{doc_id}/versions", response_class=HTMLResponse)
def docs_versions(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)
    svc = DocService(db)
    versions = svc.list_doc_versions(project_id, doc_id)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_version_drawer.html",
        {"versions": versions, "doc_id": doc_id, "project_id": project_id},
    )


# ---------------------------------------------------------------------------
# Doc generation job routes
# ---------------------------------------------------------------------------

_STREAM_TIMEOUT_SECONDS = 15 * 60


@router.post("/api/project/{id}/docs/{doc_id}/generate")
def docs_generate(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Create a DocGenerationJob for the given doc.

    Returns htmx-compatible HTML fragment that replaces the Generate button with a spinner.
    If a job is already running for this doc, returns 409.
    """
    _get_project_or_404(project_id, db)
    svc = DocService(db)

    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")

    full_doc_id = f"{project_id}:{doc_id}"
    from orch.db.models import DocGenerationJob

    running_count = (
        db.query(DocGenerationJob)
        .filter(
            DocGenerationJob.doc_id == full_doc_id,
            DocGenerationJob.status == JobStatus.running,
        )
        .count()
    )

    if running_count > 0:
        return JSONResponse(
            {"error": "Generation already in progress"},
            status_code=409,
        )

    job = svc.create_doc_job(project_id, doc_id)

    templates: Jinja2Templates = request.app.state.templates
    response = templates.TemplateResponse(
        request,
        "fragments/docs_generate_running.html",
        {"job": job, "doc_id": doc_id, "project_id": project_id},
    )
    response.headers["HX-Trigger"] = (
        f'{{"docJobCreated": {{"job_id": "{job.id}", "doc_id": "{doc_id}"}}}}'
    )
    return response


async def _job_status_stream(job_id: str, request: Request) -> AsyncGenerator[str, None]:
    """Async generator that polls job status every 2 seconds and yields SSE data."""
    from orch.db.session import SessionLocal

    start_time = asyncio.get_event_loop().time()
    timeout_at = start_time + _STREAM_TIMEOUT_SECONDS

    while True:
        if asyncio.get_event_loop().time() >= timeout_at:
            yield "event: timeout\ndata: {}\n\n"
            break

        if await request.is_disconnected():
            break

        db = SessionLocal()
        try:
            from orch.db.models import DocGenerationJob

            job = db.get(DocGenerationJob, job_id)
            if job is None:
                yield "event: error\ndata: {'error': 'Job not found'}\n\n"
                break

            if job.status == JobStatus.running:
                data = f'{{"event": "status", "status": "running", "job_id": "{job_id}"}}'
                yield f"event: status\ndata: {data}\n\n"

            elif job.status == JobStatus.completed:
                doc_id_short = job.doc_id.split(":")[-1] if job.doc_id else ""
                data = (
                    f'{{"event": "completed", "status": "completed", "doc_id": "{doc_id_short}"}}'
                )
                yield f"event: completed\ndata: {data}\n\n"
                break

            elif job.status == JobStatus.failed:
                error_msg = job.error or "unknown error"
                doc_id_short = job.doc_id.split(":")[-1] if job.doc_id else ""
                data = (
                    f'{{"event": "failed", "status": "failed", '
                    f'"error": "{error_msg}", "doc_id": "{doc_id_short}"}}'
                )
                yield f"event: failed\ndata: {data}\n\n"
                break

        finally:
            db.close()

        await asyncio.sleep(2)


@router.get("/api/project/{id}/docs/jobs/{job_id}/stream")
async def docs_job_stream(
    project_id: str,
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """SSE stream for DocGenerationJob status updates.

    Events emitted:
    - status: every 2 seconds while job is running
    - completed: when job finishes successfully
    - failed: when job fails
    - timeout: after 15 minutes
    """
    _get_project_or_404(project_id, db)
    return StreamingResponse(
        _job_status_stream(job_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/api/project/{id}/docs/jobs/{job_id}/status")
def docs_job_status(
    project_id: str,
    job_id: str,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """JSON poll endpoint for DocGenerationJob status."""
    _get_project_or_404(project_id, db)
    from orch.db.models import DocGenerationJob

    job = db.get(DocGenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    duration_seconds = None
    if job.duration_seconds is not None:
        duration_seconds = job.duration_seconds
    elif job.started_at is not None and job.completed_at is not None:
        duration_seconds = int((job.completed_at - job.started_at).total_seconds())
    elif job.started_at is not None:
        duration_seconds = int((datetime.now(UTC) - job.started_at).total_seconds())

    return JSONResponse(
        {
            "job_id": job.id,
            "status": job.status.value,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "duration_seconds": duration_seconds,
            "skill_used": job.skill_used,
            "error": job.error,
        }
    )


@router.get("/api/project/{id}/docs/{doc_id}/jobs")
def docs_job_history(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: last 10 DocGenerationJob records for this doc.

    Ordered by requested_at DESC.
    """
    _get_project_or_404(project_id, db)
    from orch.db.models import DocGenerationJob

    full_doc_id = f"{project_id}:{doc_id}"
    jobs = (
        db.query(DocGenerationJob)
        .filter(DocGenerationJob.doc_id == full_doc_id)
        .order_by(DocGenerationJob.requested_at.desc())
        .limit(10)
        .all()
    )

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_job_history.html",
        {"jobs": jobs, "doc_id": doc_id, "project_id": project_id},
    )


@router.get("/api/project/{id}/docs/{doc_id}/card")
def docs_card(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: a single docs_card.html for the given doc."""
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")

    stale_docs = svc.get_stale_docs(project_id, project.repo_root)
    stale_doc_ids = {d.doc_id for d, _, _ in stale_docs}
    stale_source_map = {d.doc_id: path for d, path, _ in stale_docs}

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_card.html",
        {
            "doc": doc,
            "current_project": project,
            "stale_doc_ids": stale_doc_ids,
            "stale_source_map": stale_source_map,
        },
    )


@router.get("/api/project/{id}/docs/config", response_class=HTMLResponse)
def docs_config_get(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: render doc config panel."""
    project = _get_project_or_404(project_id, db)
    doc_config = project.config.get("doc_generation", {}) if project.config else {}
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_config_panel.html",
        {"project_id": project_id, "doc_config": doc_config},
    )


@router.post("/api/project/{id}/docs/config")
async def docs_config_post(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Save doc config to Project.config.doc_generation."""
    project = _get_project_or_404(project_id, db)
    data = await request.json()
    if "doc_generation" not in (project.config or {}):
        if project.config is None:
            project.config = {}
        project.config["doc_generation"] = {}

    cfg = project.config["doc_generation"]
    if "auto_trigger_on_merge" in data:
        cfg["auto_trigger_on_merge"] = data["auto_trigger_on_merge"]
    if "stale_threshold_hours" in data:
        cfg["stale_threshold_hours"] = int(data["stale_threshold_hours"])
    if "forbidden_phrases" in data:
        phrases = data["forbidden_phrases"]
        if isinstance(phrases, str):
            phrases = [p.strip() for p in phrases.split(",") if p.strip()]
        cfg["forbidden_phrases"] = phrases

    db.flush()
    return HTMLResponse(
        '<div class="p-4 bg-green-50 border border-green-200 rounded-lg '
        'text-sm text-green-700">Settings saved ✓</div>',
        headers={"HX-Trigger": '{"configSaved": {}}'},
    )


@router.get("/api/project/{id}/docs/stale", response_class=HTMLResponse)
def docs_stale_summary(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: stale docs summary row."""
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)
    stale_docs = svc.get_stale_docs(project_id, project.repo_root)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_stale_summary.html",
        {"project_id": project_id, "stale_count": len(stale_docs)},
    )


@router.post("/api/project/{id}/docs/regenerate-stale", response_class=HTMLResponse)
def docs_regenerate_stale(
    project_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Create jobs for all stale docs."""
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)
    stale_docs = svc.get_stale_docs(project_id, project.repo_root)
    created_count = 0
    for doc, _, _ in stale_docs:
        svc.create_doc_job(project_id, doc.doc_id, trigger_reason="user:regenerate-stale")
        created_count += 1
    return HTMLResponse(
        f'<div class="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg '
        f'text-sm text-green-700">Queued {created_count} job'
        f"{'s' if created_count != 1 else ''} for regeneration</div>",
        headers={"HX-Trigger": '{"docsRegenerated": {}}'},
    )


@router.get("/api/project/{id}/docs/{doc_id}/lint-warnings", response_class=HTMLResponse)
def docs_lint_warnings(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: lint warnings callout for doc detail page."""
    _get_project_or_404(project_id, db)
    from orch.db.models import DocGenerationJob

    full_doc_id = f"{project_id}:{doc_id}"
    job = (
        db.query(DocGenerationJob)
        .filter(
            DocGenerationJob.doc_id == full_doc_id,
            DocGenerationJob.status == JobStatus.completed,
        )
        .order_by(DocGenerationJob.completed_at.desc())
        .first()
    )

    if job is None or not job.lint_warnings:
        return HTMLResponse("")

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_lint_warnings.html",
        {"lint_warnings": job.lint_warnings},
    )
