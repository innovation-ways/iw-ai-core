"""Research router — project-level research document library and detail pages."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.utils.markdown import render_markdown
from orch.db.models import DocStatus, DocType, EditorialCategory, Project
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


@router.get("/research", response_class=HTMLResponse)
def research_library(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)
    docs = svc.list_docs(project_id, doc_type=DocType.research)
    statuses = [ds.value for ds in DocStatus]
    categories = [c.value for c in EditorialCategory]
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "research_library.html",
        {
            "current_project": project,
            "docs": docs,
            "statuses": statuses,
            "categories": categories,
        },
    )


@router.get("/research/{doc_id}", response_class=HTMLResponse)
def research_detail(
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
    if doc.doc_type != DocType.research:
        raise HTTPException(status_code=404, detail="Document not found")
    versions = svc.list_doc_versions(project_id, doc_id)
    content_html = render_markdown(doc.content) if doc.content else ""
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "research_detail.html",
        {
            "current_project": project,
            "doc": doc,
            "versions": versions,
            "content_html": content_html,
        },
    )


@router.get("/research/{doc_id}/html-view")
def research_html_view(
    project_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Serve the stored branded HTML file, or render markdown on-the-fly as fallback."""
    _get_project_or_404(project_id, db)
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    if doc.doc_type != DocType.research:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.content is None:
        raise HTTPException(status_code=404, detail="No content available")

    if doc.html_path and Path(doc.html_path).exists():
        html_bytes = Path(doc.html_path).read_bytes()
        from fastapi.responses import Response

        return Response(content=html_bytes, media_type="text/html")

    rendered = render_markdown(doc.content)
    fallback_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{doc.title}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 860px; margin: 40px auto; padding: 0 24px;
         color: #0F172A; line-height: 1.6; }}
  h1,h2,h3 {{ color: #1E293B; }} h2 {{ border-bottom: 1px solid #E2E8F0; padding-bottom: 6px; }}
  table {{ border-collapse: collapse; width: 100%; }} th,td {{ border: 1px solid #E2E8F0; padding: 8px 12px; }}
  th {{ background: #F1F5F9; }} img {{ max-width: 100%; }}
  code {{ background: #F1F5F9; padding: 2px 5px; border-radius: 3px; font-size: 0.875em; }}
  pre {{ background: #F1F5F9; padding: 16px; border-radius: 6px; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; }}
</style>
</head>
<body>{rendered}</body>
</html>"""
    from fastapi.responses import Response

    return Response(content=fallback_html, media_type="text/html")
