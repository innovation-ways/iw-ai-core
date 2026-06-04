"""Research router — project-level research document library and detail pages."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.utils.markdown import render_markdown
from orch.db.models import DocStatus, DocType, EditorialCategory, Project, ProjectDoc
from orch.doc_service import DocService

_SORT_KEYS: dict[str, Any] = {
    "doc_id": lambda d: d.doc_id or "",
    "title": lambda d: (d.title or "").lower(),
    "editorial_category": lambda d: d.editorial_category.value if d.editorial_category else "",
    "status": lambda d: d.status.value if d.status else "",
    "created_at": lambda d: d.created_at,
}


def _sort_docs(docs: list[ProjectDoc], sort: str, sort_dir: str) -> list[ProjectDoc]:
    """Sort a list of ProjectDoc using the registered sort key.

    Args:
        docs: Documents to sort.
        sort: Key name from _SORT_KEYS ('doc_id', 'title', etc.).
        sort_dir: 'asc' or 'desc'.

    Returns:
        New list sorted according to the specified key and direction.
    """
    key = _SORT_KEYS.get(sort, _SORT_KEYS["doc_id"])
    return sorted(docs, key=key, reverse=(sort_dir == "desc"))


if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/project/{project_id}")


def _get_project_or_404(project_id: str, db: Session) -> Project:
    """Fetch a project by ID or raise HTTP 404.

    Args:
        project_id: The project identifier to look up.
        db: Active database session.

    Returns:
        The matching Project ORM row.

    Raises:
        HTTPException: With status 404 if the project does not exist.
    """
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")
    return project


@router.get("/research", response_class=HTMLResponse)
def research_library(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    sort: str = "doc_id",
    sort_dir: str = "desc",
) -> Any:
    """Render the research document library page for a project.

    Args:
        project_id: The project whose research documents are listed.
        request: The current FastAPI request.
        db: Active database session.
        sort: Sort key — one of doc_id, title, editorial_category, status, created_at.
        sort_dir: Sort direction — 'asc' or 'desc'.

    Returns:
        Full HTML research library page with sortable document table.
    """
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)
    raw_docs = svc.list_docs(project_id, doc_type=DocType.research)
    valid_sort = sort if sort in _SORT_KEYS else "doc_id"
    valid_dir = sort_dir if sort_dir in ("asc", "desc") else "desc"
    docs = _sort_docs(raw_docs, valid_sort, valid_dir)
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
            "sort": valid_sort,
            "sort_dir": valid_dir,
            "current_status": "",
            "current_category": "",
            "current_q": "",
        },
    )


@router.get("/research/{doc_id}", response_class=HTMLResponse)
def research_detail(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Render the research document detail page.

    Args:
        project_id: The project that owns the document.
        doc_id: The document identifier.
        request: The current FastAPI request.
        db: Active database session.

    Returns:
        Full HTML research detail page with rendered markdown and version history.
    """
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
  table {{ border-collapse: collapse; width: 100%; }}
  th,td {{ border: 1px solid #E2E8F0; padding: 8px 12px; }}
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


@router.get("/api/research/search", response_class=HTMLResponse)
def research_search(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    q: str | None = None,
    status: str | None = None,
    category: str | None = None,
    sort: str = "doc_id",
    sort_dir: str = "asc",
) -> Any:
    """Return a filtered, sorted research search results fragment.

    Args:
        project_id: The project to search within.
        request: The current FastAPI request.
        db: Active database session.
        q: Optional full-text search query.
        status: Optional doc status filter.
        category: Optional editorial category filter.
        sort: Sort key — one of doc_id, title, editorial_category, status, created_at.
        sort_dir: Sort direction — 'asc' or 'desc'.

    Returns:
        HTML fragment with matching research document rows.
    """
    project = _get_project_or_404(project_id, db)
    svc = DocService(db)

    status_enum: DocStatus | None = None
    if status:
        for ds in DocStatus:
            if ds.value == status:
                status_enum = ds
                break

    category_enum: EditorialCategory | None = None
    if category:
        for ec in EditorialCategory:
            if ec.value == category:
                category_enum = ec
                break

    raw_docs = svc.list_docs(
        project_id,
        doc_type=DocType.research,
        status=status_enum,
        search=q,
    )

    if category_enum:
        raw_docs = [d for d in raw_docs if d.editorial_category == category_enum]

    valid_sort = sort if sort in _SORT_KEYS else "doc_id"
    valid_dir = sort_dir if sort_dir in ("asc", "desc") else "asc"
    docs = _sort_docs(raw_docs, valid_sort, valid_dir)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/research_search_results.html",
        {
            "docs": docs,
            "current_project": project,
            "sort": valid_sort,
            "sort_dir": valid_dir,
            "current_status": status or "",
            "current_category": category or "",
            "current_q": q or "",
        },
    )
