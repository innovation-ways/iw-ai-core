"""Research router — project-level research document library and detail pages."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.utils.markdown import (
    render_markdown_with_callouts,
    render_pdf_chromium,
)
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
    # render_mermaid=False keeps Mermaid as code blocks for the client-side runtime
    # (research_detail.html shim), but D2 blocks are always server-rendered to SVG
    # because D2 has no browser renderer; callouts are styled here too.
    content_html = (
        render_markdown_with_callouts(doc.content, render_mermaid=False, project_id=project_id)
        if doc.content
        else ""
    )
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

    # Standalone iframe served without the Mermaid client runtime, so render all
    # diagrams (Mermaid + D2) server-side to inline SVG.
    rendered = render_markdown_with_callouts(doc.content, project_id=project_id)
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


def _get_research_doc_or_404(project_id: str, doc_id: str, db: Session) -> ProjectDoc:
    """Fetch a research document by ID or raise HTTP 404.

    Args:
        project_id: The project that owns the document.
        doc_id: The document identifier.
        db: Active database session.

    Returns:
        The matching research ProjectDoc row (doc_type=research, with content).

    Raises:
        HTTPException: 404 when the doc is missing, is not a research doc, or has no content.
    """
    svc = DocService(db)
    doc = svc.get_doc(project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    if doc.doc_type != DocType.research:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.content is None:
        raise HTTPException(status_code=404, detail="No content to generate PDF from")
    return doc


def _render_research_pdf_cached(
    project: Project, doc: ProjectDoc, request: Request, db: Session
) -> bytes | None:
    """Render a research document to PDF bytes, caching the result on disk.

    Returns the cached PDF when one exists for the current doc version; otherwise
    renders the markdown content through the shared branded PDF template and
    Chromium worker, caches the result keyed by doc version, and returns the bytes.

    Args:
        project: The project that owns the document (provides the cache repo_root).
        doc: The research document to render (must have non-None content).
        request: The current FastAPI request (used to resolve templates).
        db: Active database session (used to persist the cache path).

    Returns:
        The rendered PDF bytes, or ``None`` when the Chromium worker is unavailable.
    """
    # Use cached PDF if available
    if doc.pdf_path and Path(doc.pdf_path).exists():
        return Path(doc.pdf_path).read_bytes()

    templates: Jinja2Templates = request.app.state.templates
    pdf_template = templates.get_template("pdf/doc_pdf.html")
    html_content = pdf_template.render(
        doc=doc,
        project=project,
        rendered_content=render_markdown_with_callouts(doc.content or "", project_id=project.id),
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
    )

    pdf_bytes = render_pdf_chromium(html_content)
    if pdf_bytes is None:
        return None

    # Cache to disk keyed by doc version
    cache_dir = Path(project.repo_root) / "docs" / ".generated" / project.id
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{doc.doc_id}-v{doc.version}.pdf"
        cache_file.write_bytes(pdf_bytes)
        DocService(db).update_doc(project.id, doc.doc_id, pdf_path=str(cache_file))
        db.commit()
    except Exception:  # noqa: BLE001 — read-only fs, permission error, etc.
        import logging

        logging.getLogger(__name__).warning(
            "Failed to write pdf_path cache for research doc %s/%s", project.id, doc.doc_id
        )
    return pdf_bytes


@router.get("/research/{doc_id}/pdf-view")
def research_pdf_view(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Serve a research PDF inline for embedding in an iframe (no attachment header)."""
    project = _get_project_or_404(project_id, db)
    doc = _get_research_doc_or_404(project_id, doc_id, db)

    pdf_bytes = _render_research_pdf_cached(project, doc, request, db)
    if pdf_bytes is None:
        # Styled HTML fallback so the iframe shows a message, not a blank screen.
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

    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/research/{doc_id}/pdf")
def research_pdf(
    project_id: str,
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Generate and serve a research PDF download (with Content-Disposition: attachment).

    Args:
        project_id: The project the document belongs to.
        doc_id: The research document to export as PDF.
        request: The current FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        A PDF binary response with a download filename header, or 503 JSON when
        Chromium is unavailable.

    Raises:
        HTTPException: 404 when the document, its content, or its research type does not match.
    """
    project = _get_project_or_404(project_id, db)
    doc = _get_research_doc_or_404(project_id, doc_id, db)

    pdf_bytes = _render_research_pdf_cached(project, doc, request, db)
    if pdf_bytes is None:
        return JSONResponse(
            {
                "error": "PDF generation unavailable",
                "detail": "Chromium binary not found — check _PLAYWRIGHT_CHROME path",
            },
            status_code=503,
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{doc.slug}-v{doc.version}.pdf"'},
    )


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
