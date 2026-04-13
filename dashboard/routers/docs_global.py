"""Global documentation search router — cross-project docs discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from orch.db.models import DocStatus, DocTier, DocType, Project
from orch.doc_service import DocService

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/docs", response_class=HTMLResponse)
def docs_global_page(
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    projects = list(db.scalars(select(Project).order_by(Project.display_name)).all())
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "docs_global.html",
        {
            "projects": projects,
            "results_by_project": {},
            "query": "",
        },
    )


@router.get("/api/docs/search", response_class=HTMLResponse)
def docs_global_search(
    request: Request,
    db: Session = Depends(get_db),
    q: str = "",
    doc_type: str | None = None,
    status: str | None = None,
    tier: str | None = None,
    project_id: str | None = None,
) -> Any:
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

    tier_enum: DocTier | None = None
    if tier:
        for t in DocTier:
            if t.value == tier:
                tier_enum = t
                break

    results: list[tuple[Any, str]] = []
    if q.strip():
        results = svc.search_docs_global(
            search=q,
            doc_type=doc_type_enum,
            status=status_enum,
            tier=tier_enum,
            project_id=project_id or None,
        )

    results_by_project: dict[str, list[dict[str, Any]]] = {}
    for doc, snippet in results:
        pid = doc.project_id
        if pid not in results_by_project:
            results_by_project[pid] = []
        results_by_project[pid].append({"doc": doc, "snippet": snippet})

    project_ids = list(results_by_project.keys())
    project_map: dict[str, Project] = {}
    if project_ids:
        projects = db.scalars(select(Project).where(Project.id.in_(project_ids))).all()
        project_map = {p.id: p for p in projects}

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/docs_global_results.html",
        {
            "results_by_project": results_by_project,
            "project_map": project_map,
            "query": q,
        },
    )
