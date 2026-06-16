"""Docs router — project-level documentation library and detail pages."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.utils.branding import (
    brand_colors,
    brand_lockup_html,
    inter_font_face_css,
)
from dashboard.utils.markdown import render_markdown_with_callouts, render_pdf_chromium
from orch.db.models import DocStatus, DocType, JobStatus, Project
from orch.doc_service import DocService

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/project/{project_id}")


def _normalize_doc_content_for_render(doc: Any) -> str:
    """Normalise bare-DSL diagram-doc content into a fenced mermaid block.

    ``doc_type=diagram`` docs from the code-mapping pipeline (mapgen.py) are
    stored as ``<!-- purpose: ... -->\n<bare Mermaid DSL>`` — no
    `` ```mermaid `` fence.  This helper wraps them in one so both the
    client-side shim and the server-side renderer recognise them as diagrams.

    Conservative (idempotent):
      * only touches ``doc_type==DocType.diagram`` docs
      * only wraps when no `` ```mermaid `` fence is already present
      * strips a leading ``<!-- purpose: ... -->`` HTML comment (and
        surrounding blank lines) before wrapping, so the purpose text does
        not leak into the DSL and confuse Mermaid.
    """
    if doc.doc_type != DocType.diagram:
        return doc.content or ""
    content = doc.content or ""
    if "```mermaid" in content:
        return content
    # Strip leading <!-- purpose: ... --> comment and surrounding blank lines
    stripped = re.sub(r"^<!--[\s\S]*?-->\s*", "", content, count=1).lstrip("\n")
    return f"```mermaid\n{stripped}\n```"


def _get_project_or_404(project_id: str, db: Session) -> Project:
    """Fetch a Project by id or raise HTTP 404.

    Args:
        project_id: Identifier of the project to look up.
        db: Active database session.

    Returns:
        The matching Project row.

    Raises:
        HTTPException: 404 when no project with the given id exists.
    """
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
    """Render the docs library page listing all non-research documents for a project.

    Args:
        project_id: Project whose document catalogue is displayed.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        Full-page HTML response for ``docs_library.html``.
    """
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)
    docs = [d for d in svc.list_docs(project_id) if d.doc_type != DocType.research]
    doc_types = [dt.value for dt in DocType if dt != DocType.research]
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
    """Render the document detail page with rendered content and version list.

    Args:
        project_id: Project the document belongs to.
        doc_id: Document identifier to display.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        Full-page HTML response for ``docs_detail.html``.

    Raises:
        HTTPException: 404 when the document does not exist.
    """
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    versions = svc.list_doc_versions(project_id, doc_id)
    normalized_content = _normalize_doc_content_for_render(doc)
    content_html = (
        render_markdown_with_callouts(normalized_content, render_mermaid=False)
        if normalized_content
        else ""
    )
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


@router.get("/docs/{doc_id}/html-view")
def docs_html_view(
    project_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """Serve the stored branded HTML file, or render markdown on-the-fly as fallback.

    When rendering on-the-fly the result is cached to ``ProjectDoc.html_path``
    (keyed by doc version) so repeat views are instant.
    """
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    if doc.content is None:
        raise HTTPException(status_code=404, detail="No content available")

    # Prefer the pre-generated HTML file on disk
    if doc.html_path and Path(doc.html_path).exists():
        html_bytes = Path(doc.html_path).read_bytes()
        return Response(content=html_bytes, media_type="text/html")

    # Fallback: render markdown inline with brand styling (Innovation Ways
    # palette + embedded Inter + logo lockup) so the on-the-fly HTML view is
    # on-brand and consistent with the PDF output.
    normalized_content = _normalize_doc_content_for_render(doc)
    rendered = render_markdown_with_callouts(normalized_content, render_mermaid=True)
    colors = brand_colors()
    ink = colors.get("ink", "#1A1D23")
    accent = colors.get("accent", "#0D9488")
    accent_strong = colors.get("accentStrong", "#115E59")
    accent_tint = colors.get("accentTint", "#F0FDFA")
    border = colors.get("border", "#E2E8F0")
    font_face = inter_font_face_css()
    lockup = brand_lockup_html()
    fallback_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{doc.title}</title>
<style>
  {font_face}
  body {{ font-family: 'Inter', system-ui, sans-serif; max-width: 860px; margin: 40px auto;
         padding: 0 24px; color: {ink}; line-height: 1.6; }}
  .iw-lockup {{ display: inline-flex; align-items: center; gap: 8px; margin-bottom: 24px;
         padding-bottom: 16px; border-bottom: 2px solid {accent}; width: 100%; }}
  .iw-lockup-mark svg {{ height: 26px; width: 26px; display: block; }}
  .iw-lockup-name {{ font-family: 'Space Grotesk','Inter',system-ui,sans-serif; font-weight: 600;
         font-size: 15px; letter-spacing: -0.01em; color: {ink}; }}
  h1,h2,h3,h4 {{ font-family: 'Space Grotesk','Inter',system-ui,sans-serif; color: {ink};
         letter-spacing: -0.01em; }}
  h2 {{ border-bottom: 1px solid {border}; padding-bottom: 6px; }}
  a {{ color: {accent_strong}; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th,td {{ border: 1px solid {border}; padding: 8px 12px; }}
  th {{ background: {accent_tint}; color: {accent_strong}; }} img {{ max-width: 100%; }}
  blockquote {{ border-left: 3px solid {accent}; padding-left: 1em; color: #71757E; }}
  code {{ background: #F1F5F9; padding: 2px 5px; border-radius: 3px; font-size: 0.875em; }}
  pre {{ background: #F1F5F9; padding: 16px; border-radius: 6px; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; }}
  .mermaid-diagram svg {{ max-width: 100%; height: auto; }}
</style>
</head>
<body>{lockup}{rendered}</body>
</html>"""

    # Cache to disk only when mmdc succeeded (no raw mermaid block fell through)
    if 'class="language-mermaid"' not in fallback_html:
        cache_dir = Path(project.repo_root) / "docs" / ".generated" / project_id
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / f"{doc_id}-v{doc.version}.html"
            cache_file.write_bytes(fallback_html.encode("utf-8"))
            svc.update_doc(project_id, doc_id, html_path=str(cache_file))
            db.commit()
        except Exception:  # noqa: BLE001 — read-only fs, permission error, etc.
            import logging

            logging.getLogger(__name__).warning(
                "Failed to write html_path cache for doc %s/%s", project_id, doc_id
            )

    return Response(content=fallback_html, media_type="text/html")


@router.get("/docs/{doc_id}/pdf-view")
def docs_pdf_view(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Serve PDF inline for embedding in an iframe (no Content-Disposition: attachment)."""
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    if doc.content is None:
        raise HTTPException(status_code=404, detail="No content to generate PDF from")

    # Use cached PDF if available
    if doc.pdf_path and Path(doc.pdf_path).exists():
        pdf_bytes = Path(doc.pdf_path).read_bytes()
        return Response(content=pdf_bytes, media_type="application/pdf")

    # Generate on-the-fly
    templates: Jinja2Templates = request.app.state.templates
    pdf_template = templates.get_template("pdf/doc_pdf.html")
    normalized_content = _normalize_doc_content_for_render(doc)
    html_content = pdf_template.render(
        doc=doc,
        project=project,
        rendered_content=render_markdown_with_callouts(normalized_content),
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
    )

    pdf_bytes = cast("bytes", render_pdf_chromium(html_content))
    if pdf_bytes is None:
        # Return a styled HTML page instead of a bare 503 so the iframe shows
        # a meaningful message rather than a blank screen.
        unavailable_html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PDF unavailable</title>
<style>
  body { font-family: system-ui, sans-serif; display: flex; align-items: center;
         justify-content: center; min-height: 100vh; margin: 0;
         background: #f8fafc; }
  .card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
          padding: 32px 40px; max-width: 440px; text-align: center;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  h2 { color: #1e293b; font-size: 1.125rem; margin: 0 0 12px; }
  p  { color: #64748b; font-size: 0.9rem; line-height: 1.5; margin: 0 0 20px; }
  .hint { background: #f1f5f9; border-radius: 6px; padding: 12px;
           font-size: 0.8rem; color: #475569; }
</style>
</head>
<body>
<div class="card">
  <h2>PDF unavailable</h2>
  <p>Chromium binary not found on this server. The HTML view is accessible below.</p>
  <div class="hint">Install Chromium or check the
   <code>_PLAYWRIGHT_CHROME</code> environment variable.</div>
</div>
</body>
</html>"""
        return Response(content=unavailable_html, media_type="text/html", status_code=200)

    # Cache to disk keyed by doc version
    cache_dir = Path(project.repo_root) / "docs" / ".generated" / project_id
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{doc_id}-v{doc.version}.pdf"
        cache_file.write_bytes(pdf_bytes)
        svc.update_doc(project_id, doc_id, pdf_path=str(cache_file))
        db.commit()
    except Exception:  # noqa: BLE001 — read-only fs, permission error, etc.
        import logging

        logging.getLogger(__name__).warning(
            "Failed to write pdf_path cache for doc %s/%s", project_id, doc_id
        )

    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/docs/{doc_id}/pdf")
def docs_pdf(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Generate and serve a PDF download (with Content-Disposition: attachment).

    Args:
        project_id: Project the document belongs to.
        doc_id: Document to export as PDF.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        PDF binary response with a download filename header, or 503 JSON when
        Chromium is unavailable.

    Raises:
        HTTPException: 404 when the document or its content does not exist.
    """
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
    normalized_content = _normalize_doc_content_for_render(doc)
    html_content = pdf_template.render(
        doc=doc,
        project=project,
        rendered_content=render_markdown_with_callouts(normalized_content),
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
    )

    pdf_bytes = cast("bytes", render_pdf_chromium(html_content))
    if pdf_bytes is None:
        return JSONResponse(
            {
                "error": "PDF generation unavailable",
                "detail": "Chromium binary not found — check _PLAYWRIGHT_CHROME path",
            },
            status_code=503,
        )

    cache_dir = Path(project.repo_root) / "docs" / ".generated" / project_id
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{doc_id}-v{doc.version}.pdf"
        cache_file.write_bytes(pdf_bytes)
        svc.update_doc(project_id, doc_id, pdf_path=str(cache_file))
        db.commit()
    except Exception:  # noqa: BLE001 — read-only fs, permission error, etc.
        import logging

        logging.getLogger(__name__).warning(
            "Failed to write pdf_path cache for doc %s/%s", project_id, doc_id
        )

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
    """htmx fragment: filtered and searched docs result rows.

    Args:
        project_id: Project to search within.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.
        q: Free-text search query passed to DocService.
        doc_type: Optional doc type filter string.
        status: Optional doc status filter string.

    Returns:
        HTML fragment for ``fragments/docs_search_results.html``.
    """
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

    docs = [
        d
        for d in svc.list_docs(
            project_id,
            doc_type=doc_type_enum,
            status=status_enum,
            search=q,
        )
        if doc_type_enum is not None or d.doc_type != DocType.research
    ]
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
    """htmx fragment: version drawer listing all versions for a document.

    Args:
        project_id: Project the document belongs to.
        doc_id: Document whose version list is returned.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        HTML fragment for ``fragments/docs_version_drawer.html``.
    """
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


@router.post("/api/docs/{doc_id}/generate")
def docs_generate(
    project_id: str,
    doc_id: str,
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
    db.commit()

    import json

    disabled_btn = (
        "<button disabled "
        'class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-muted text-muted-foreground '
        'rounded-md text-sm font-medium cursor-not-allowed opacity-60 select-none" '
        'aria-label="Generation queued">'
        '<svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4">'
        "</circle>"
        '<path class="opacity-75" fill="currentColor" '
        'd="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 '
        '3.042 1.135 5.824 3 7.938l3-2.647z"></path>'
        "</svg>"
        "Queued…"
        "</button>"
    )
    response = HTMLResponse(disabled_btn)
    response.headers["HX-Trigger"] = json.dumps(
        {
            "docJobCreated": {"job_id": job.id, "doc_id": doc_id},
            "runningJobsReload": None,
        }
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


@router.get("/api/docs/jobs/{job_id}/stream")
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


@router.get("/api/docs/jobs/{job_id}/status")
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


@router.get("/api/docs/jobs/{job_id}/panel", response_class=HTMLResponse)
def docs_job_panel(
    project_id: str,
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: SSE status panel for a running DocGenerationJob."""
    _get_project_or_404(project_id, db)
    from orch.db.models import DocGenerationJob

    job = db.get(DocGenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_job_status.html",
        {"job_id": job_id, "project_id": project_id},
    )


@router.delete("/api/docs/jobs/{job_id}", response_class=HTMLResponse)
def docs_job_cancel(
    project_id: str,
    job_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Cancel a running DocGenerationJob."""
    _get_project_or_404(project_id, db)
    from orch.db.models import DocGenerationJob

    job = db.get(DocGenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    if job.status != JobStatus.running:
        raise HTTPException(status_code=409, detail="Job is not running")
    job.status = JobStatus.failed
    job.error = "Cancelled by user"
    db.commit()
    return HTMLResponse("")


@router.get("/api/docs/running-jobs", response_class=HTMLResponse)
def docs_running_jobs(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: running and recently-failed DocGenerationJob rows for the project.

    Returns jobs with status==running, plus jobs with status==failed whose
    completed_at falls within roughly the last 10 minutes.  Jobs older than that
    window (e.g. user-cancelled jobs that have no completed_at, or very old
    failures) are not included.  Within the result set running jobs are ordered
    first, then failed jobs — both sorted by requested_at ascending.
    """
    _get_project_or_404(project_id, db)
    from orch.db.models import DocGenerationJob, DocType, ProjectDoc

    # 10-minute cutoff for failed jobs to show in the strip
    recently_failed_cutoff = datetime.now(UTC) - timedelta(minutes=10)

    # Build a union: running jobs + recently-failed jobs.
    # Ordering: running jobs first (requested_at ASC), then failed jobs
    # (requested_at ASC within the failed group — requested_at is set at job
    # creation so this is deterministic and stable).  We implement this with a
    # computed priority column so both groups are returned in a single query
    # with a stable sort.
    from sqlalchemy import and_, case, or_

    priority = case(
        (DocGenerationJob.status == JobStatus.running, 0),
        else_=1,
    )

    jobs = (
        db.query(DocGenerationJob)
        .join(ProjectDoc, DocGenerationJob.doc_id == ProjectDoc.id)
        .filter(
            DocGenerationJob.doc_id.startswith(f"{project_id}:"),
            ProjectDoc.doc_type != DocType.research,
            or_(
                DocGenerationJob.status == JobStatus.running,
                and_(
                    DocGenerationJob.status == JobStatus.failed,
                    DocGenerationJob.completed_at >= recently_failed_cutoff,
                ),
            ),
        )
        .order_by(priority.asc(), DocGenerationJob.requested_at.asc())
        .all()
    )

    svc = DocService(db)
    running_jobs: list[dict[str, Any]] = []
    for job in jobs:
        doc_id_short = job.doc_id.split(":")[-1] if job.doc_id else ""
        doc = svc.get_doc(project_id, doc_id_short)
        running_jobs.append(
            {
                "job_id": job.id,
                "doc_id": doc_id_short,
                "doc_title": doc.title if doc else doc_id_short,
                "status": job.status.value,
                "error": job.error or "",
            }
        )
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_running_jobs.html",
        {"running_jobs": running_jobs, "project_id": project_id},
    )


@router.get("/api/docs/{doc_id}/jobs")
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


@router.get("/api/docs/{doc_id}/card")
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


@router.get("/api/docs/config", response_class=HTMLResponse)
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


@router.post("/api/docs/config")
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

    db.commit()
    return HTMLResponse(
        '<div class="p-4 bg-green-50 border border-green-200 rounded-lg '
        'text-sm text-green-700">Settings saved ✓</div>',
        headers={"HX-Trigger": '{"configSaved": {}}'},
    )


@router.get("/api/docs/stale", response_class=HTMLResponse)
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


@router.post("/api/docs/regenerate-stale", response_class=HTMLResponse)
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
    db.commit()
    return HTMLResponse(
        f'<div class="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg '
        f'text-sm text-green-700">Queued {created_count} job'
        f"{'s' if created_count != 1 else ''} for regeneration</div>",
        headers={"HX-Trigger": '{"docsRegenerated": {}}'},
    )


@router.post("/api/docs/regenerate-all", response_class=HTMLResponse)
def docs_regenerate_all(
    project_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Create generation jobs for every doc in the project, skipping in-flight ones.

    Iterates the project's full doc catalogue and enqueues a DocGenerationJob for
    each document that does not already have a running or queued job, so clicking
    the button repeatedly never double-queues the same doc.

    Args:
        project_id: Project identifier.
        db: Request-scoped DB session.

    Returns:
        htmx HTML fragment summarising how many jobs were queued, with an
        ``HX-Trigger`` so the running-jobs strip reloads.
    """
    import json

    from orch.db.models import DocGenerationJob

    _get_project_or_404(project_id, db)
    svc = DocService(db)

    # Pull the whole catalogue — a large limit so big projects aren't truncated.
    # Exclude research docs to match exactly what the docs-library list shows.
    all_docs = [
        d for d in svc.list_docs(project_id, limit=10_000) if d.doc_type != DocType.research
    ]

    active_doc_ids = {
        row[0]
        for row in db.query(DocGenerationJob.doc_id)
        .filter(
            DocGenerationJob.project_id == project_id,
            DocGenerationJob.status.in_([JobStatus.queued, JobStatus.running]),
        )
        .all()
    }

    created_count = 0
    skipped_count = 0
    for doc in all_docs:
        if doc.id in active_doc_ids:
            skipped_count += 1
            continue
        svc.create_doc_job(project_id, doc.doc_id, trigger_reason="user:regenerate-all")
        created_count += 1
    db.commit()

    skipped_note = f" ({skipped_count} already in progress)" if skipped_count else ""
    return HTMLResponse(
        f'<div class="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg '
        f'text-sm text-green-700">Queued {created_count} job'
        f"{'s' if created_count != 1 else ''} for regeneration{skipped_note}</div>",
        headers={"HX-Trigger": json.dumps({"docsRegenerated": {}, "runningJobsReload": None})},
    )


@router.get("/api/docs/{doc_id}/diff", response_class=HTMLResponse)
def docs_diff(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    v1: int = 0,
    v2: int = 0,
) -> Any:
    """htmx fragment: unified diff between two document versions.

    Args:
        project_id: Project the document belongs to.
        doc_id: Document to diff.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.
        v1: Older version number; must be less than v2.
        v2: Newer version number.

    Returns:
        HTML fragment for ``fragments/docs_diff.html``.

    Raises:
        HTTPException: 422 when v1 >= v2, or 404 when the document or
            a version is not found.
    """
    _get_project_or_404(project_id, db)
    if v1 >= v2:
        raise HTTPException(
            status_code=422,
            detail=f"v1 ({v1}) must be less than v2 ({v2})",
        )
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    try:
        diff_lines = svc.diff_versions(project_id, doc_id, v1, v2)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_diff.html",
        {
            "diff_lines": diff_lines,
            "v1": v1,
            "v2": v2,
            "doc_id": doc_id,
            "project_id": project_id,
        },
    )


@router.get("/api/docs/{doc_id}/diff/sections")
def docs_diff_sections(
    project_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
    v1: int = 0,
    v2: int = 0,
) -> Any:
    """Return a structured section-level diff as JSON."""
    _get_project_or_404(project_id, db)
    if v1 >= v2:
        raise HTTPException(status_code=422, detail=f"v1 ({v1}) must be less than v2 ({v2})")
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    from sqlalchemy import select as sa_select

    from orch.db.models import ProjectDocVersion

    def _get_ver(v: int) -> str:
        composite = f"{project_id}:{doc_id}"
        row = db.execute(
            sa_select(ProjectDocVersion)
            .where(ProjectDocVersion.doc_id == composite)
            .where(ProjectDocVersion.version == v)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Version {v} not found for doc '{doc_id}'")
        return row.content or ""

    old_content = _get_ver(v1)
    new_content = _get_ver(v2)
    from orch.doc_diff import DocDiff, diff_document_versions

    result: DocDiff = diff_document_versions(old_content, new_content, v1, v2)
    return {
        "version_old": result.version_old,
        "version_new": result.version_new,
        "sections": [
            {
                "section_name": s.section_name,
                "status": s.status,
                "unified_diff": s.unified_diff,
            }
            for s in result.sections
        ],
    }


@router.get("/api/docs/{doc_id}/diff/sections/{section_name}", response_class=HTMLResponse)
def docs_diff_section(
    project_id: str,
    doc_id: str,
    section_name: str,
    request: Request,
    db: Session = Depends(get_db),
    v1: int = 0,
    v2: int = 0,
) -> Any:
    """Return an HTML fragment showing the unified diff for a single named section."""
    import urllib.parse

    section_name = urllib.parse.unquote(section_name)
    _get_project_or_404(project_id, db)
    if v1 >= v2:
        raise HTTPException(status_code=422, detail="v1 must be less than v2")
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    from sqlalchemy import select as sa_select

    from orch.db.models import ProjectDocVersion

    def _get_ver(v: int) -> str:
        composite = f"{project_id}:{doc_id}"
        row = db.execute(
            sa_select(ProjectDocVersion)
            .where(ProjectDocVersion.doc_id == composite)
            .where(ProjectDocVersion.version == v)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Version {v} not found for doc '{doc_id}'")
        return row.content or ""

    old_content = _get_ver(v1)
    new_content = _get_ver(v2)
    from orch.doc_diff import diff_document_versions

    result = diff_document_versions(old_content, new_content, v1, v2)
    section_diff = next((s for s in result.sections if s.section_name == section_name), None)
    if section_diff is None:
        raise HTTPException(status_code=404, detail=f"Section '{section_name}' not found in diff")
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_diff.html",
        {
            "diff_lines": section_diff.unified_diff,
            "v1": v1,
            "v2": v2,
            "doc_id": doc_id,
            "project_id": project_id,
        },
    )


@router.get("/api/docs/{doc_id}/diff/ai-summary")
def docs_diff_ai_summary(
    project_id: str,
    doc_id: str,  # noqa: ARG001
    db: Session = Depends(get_db),
    v1: int = 0,  # noqa: ARG001
    v2: int = 0,  # noqa: ARG001
) -> Any:
    """Stub endpoint for AI-powered diff summarization (F-00025 not yet shipped).

    Always returns HTTP 204 with X-Stub header until F-00025 provides the
    real implementation. No body is returned. Callers should handle 204 gracefully.
    """
    from fastapi.responses import Response

    _get_project_or_404(project_id, db)
    return Response(
        status_code=204,
        headers={"X-Stub": "waiting-for-F-00025"},
    )


def _make_render_pdf_fn() -> Any:
    """Return the PDF rendering callable for use in export helpers."""
    return render_pdf_chromium


@router.get("/api/docs/export")
def docs_export_bundle(
    project_id: str,
    db: Session = Depends(get_db),
    doc_ids: str = "",
) -> StreamingResponse:
    """Stream a ZIP export of one or more project documents (HTML + PDF).

    Args:
        project_id: Project to export documents from.
        db: Active database session.
        doc_ids: Comma-separated list of doc ids to include; when empty all
            documents in the project are exported.

    Returns:
        Streaming ZIP response with ``Content-Disposition: attachment``.

    Raises:
        HTTPException: 422 when no valid doc_ids are provided.
    """
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)

    if doc_ids.strip():
        raw_ids = [d.strip() for d in doc_ids.split(",") if d.strip()]
        full_ids = [f"{project_id}:{d}" for d in raw_ids]
    else:
        docs = svc.list_docs(project_id)
        full_ids = [doc.id for doc in docs]

    if not full_ids:
        raise HTTPException(status_code=422, detail="No valid doc_ids provided")

    def _render_html_for_export(content: str, doc: Any) -> str:
        # Replicate the normalisation logic using only the content string.
        # This mirrors _normalize_doc_content_for_render but works on the
        # raw content string passed by export_bundle's signature.
        if doc.doc_type == DocType.diagram and "```mermaid" not in content:
            stripped = re.sub(r"^<!--[\s\S]*?-->\s*", "", content, count=1).lstrip("\n")
            content = f"```mermaid\n{stripped}\n```"
        return render_markdown_with_callouts(content)

    zip_bytes = svc.export_bundle(
        project_id,
        full_ids,
        render_html_fn=_render_html_for_export,
        render_pdf_fn=_make_render_pdf_fn(),
    )

    import io

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{project.id}-docs-export.zip"',
        },
    )


@router.get("/api/docs/{doc_id}/export")
def docs_export_single(
    project_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream a ZIP export of a single document (HTML + PDF).

    Args:
        project_id: Project the document belongs to.
        doc_id: Document to export.
        db: Active database session.

    Returns:
        Streaming ZIP response with a versioned filename.

    Raises:
        HTTPException: 404 when the document does not exist.
    """
    _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")

    full_id = f"{project_id}:{doc_id}"

    def _render_html_for_single(content: str, _d: Any) -> str:
        if _d.doc_type == DocType.diagram and "```mermaid" not in content:
            stripped = re.sub(r"^<!--[\s\S]*?-->\s*", "", content, count=1).lstrip("\n")
            content = f"```mermaid\n{stripped}\n```"
        return render_markdown_with_callouts(content)

    zip_bytes = svc.export_bundle(
        project_id,
        [full_id],
        render_html_fn=_render_html_for_single,
        render_pdf_fn=_make_render_pdf_fn(),
    )

    import io

    slug = doc.slug or doc_id
    filename = f"{slug}-v{doc.version}.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/docs/{doc_id}/validate-links", response_class=HTMLResponse)
async def docs_validate_links(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: list broken links found in a document.

    Runs link validation in a thread to avoid blocking the event loop.

    Args:
        project_id: Project the document belongs to.
        doc_id: Document to validate links in.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        HTML fragment for ``fragments/docs_broken_links.html``.

    Raises:
        HTTPException: 404 when the document does not exist, or 422 when
            the document has no content.
    """
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    if not doc.content:
        raise HTTPException(status_code=422, detail="Document has no content to validate")

    repo_root = project.repo_root
    broken = await asyncio.to_thread(svc.validate_links, doc, repo_root)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_broken_links.html",
        {
            "broken_links": broken,
            "doc_id": doc_id,
            "project_id": project_id,
        },
    )


@router.get("/api/docs/{doc_id}/lint-warnings", response_class=HTMLResponse)
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


@router.get("/api/docs/{doc_id}/ide", response_class=HTMLResponse)
def docs_ide_tab(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: full IDE tab with guide editor and diff viewer."""
    _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_ide_tab.html",
        {
            "doc": doc,
            "doc_id": doc_id,
            "project_id": project_id,
            "current_project": _get_project_or_404(project_id, db),
        },
    )


@router.get("/api/docs/{doc_id}/guide/type", response_class=HTMLResponse)
def docs_guide_type_get(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: type guide editor panel."""
    _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    guide_md = svc.get_type_guide(doc.doc_type.value) or ""
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_guide_type_editor.html",
        {
            "doc": doc,
            "doc_id": doc_id,
            "project_id": project_id,
            "doc_type": doc.doc_type.value,
            "guide_md": guide_md,
        },
    )


@router.post("/api/docs/{doc_id}/guide/type", response_class=HTMLResponse)
def docs_guide_type_post(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    guide_md: str = Form(default=""),
) -> Any:
    """htmx endpoint: save type guide."""
    _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    svc.save_type_guide(doc.doc_type.value, guide_md)
    db.commit()
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_guide_type_editor.html",
        {
            "doc": doc,
            "doc_id": doc_id,
            "project_id": project_id,
            "doc_type": doc.doc_type.value,
            "guide_md": guide_md,
        },
    )


@router.get("/api/docs/{doc_id}/guide/instance", response_class=HTMLResponse)
def docs_guide_instance_get(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: instance guide editor panel."""
    _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    instance_guide = svc.get_instance_guide(project_id, doc_id)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_guide_instance_editor.html",
        {
            "doc": doc,
            "doc_id": doc_id,
            "project_id": project_id,
            "instance_guide": instance_guide,
        },
    )


@router.post("/api/docs/{doc_id}/guide/instance", response_class=HTMLResponse)
def docs_guide_instance_post(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    guide_md: str = Form(...),
) -> Any:
    """htmx endpoint: save instance guide."""
    _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    svc.save_instance_guide(project_id, doc_id, guide_md)
    db.commit()
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_guide_instance_editor.html",
        {
            "doc": doc,
            "doc_id": doc_id,
            "project_id": project_id,
            "instance_guide": guide_md,
        },
    )


@router.delete("/api/docs/{doc_id}/guide/instance", response_class=HTMLResponse)
def docs_guide_instance_delete(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx endpoint: delete instance guide override."""
    _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    svc.delete_instance_guide(project_id, doc_id)
    db.commit()
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_guide_instance_editor.html",
        {
            "doc": doc,
            "doc_id": doc_id,
            "project_id": project_id,
            "instance_guide": None,
        },
    )


@router.get("/api/docs/{doc_id}/guide/sections", response_class=HTMLResponse)
def docs_guide_sections_get(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: section guide list panel."""
    _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    from orch.doc_sections import extract_sections

    sections = extract_sections(doc.content or "")
    section_guides: dict[str, str] = {}
    for sg in svc.list_section_guides(project_id, doc_id):
        section_guides[sg.section_name] = sg.guide_md
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_guide_sections_panel.html",
        {
            "doc": doc,
            "doc_id": doc_id,
            "project_id": project_id,
            "sections": sections,
            "section_guides": section_guides,
        },
    )


@router.post("/api/docs/{doc_id}/guide/sections/{section_name}", response_class=HTMLResponse)
def docs_guide_section_post(
    project_id: str,
    doc_id: str,
    section_name: str,
    request: Request,
    db: Session = Depends(get_db),
    guide_md: str = Form(...),
) -> Any:
    """htmx endpoint: save a section guide."""
    _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    svc.save_section_guide(project_id, doc_id, section_name, guide_md)
    db.commit()
    from orch.doc_sections import extract_sections

    sections = extract_sections(doc.content or "")
    section_guides: dict[str, str] = {}
    for sg in svc.list_section_guides(project_id, doc_id):
        section_guides[sg.section_name] = sg.guide_md
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_guide_sections_panel.html",
        {
            "doc": doc,
            "doc_id": doc_id,
            "project_id": project_id,
            "sections": sections,
            "section_guides": section_guides,
        },
    )


@router.delete("/api/docs/{doc_id}/guide/sections/{section_name}")
def docs_guide_section_delete(
    project_id: str,
    doc_id: str,
    section_name: str,
    db: Session = Depends(get_db),
) -> Response:
    """htmx endpoint: delete a section guide."""
    _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    svc.delete_section_guide(project_id, doc_id, section_name)
    db.commit()
    return Response(status_code=204)
