"""Docs router — project-level documentation library and detail pages."""

from __future__ import annotations

import concurrent.futures
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.utils.markdown import render_markdown
from orch.db.models import DocStatus, DocType, Project
from orch.doc_service import DocService

if TYPE_CHECKING:
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
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "docs_library.html",
        {
            "current_project": project,
            "docs": docs,
            "doc_types": doc_types,
            "statuses": statuses,
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
    _get_project_or_404(project_id, db)
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
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_search_results.html",
        {"docs": docs, "current_project_id": project_id},
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
