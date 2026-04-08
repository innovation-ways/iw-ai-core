"""Global search endpoints — FTS over work_items via design_doc_search tsvector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select, text

from dashboard.dependencies import get_db
from orch.db.models import Project, WorkItem, WorkItemType

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

router = APIRouter()

_MAX_RESULTS = 50


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    project_id: str
    project_name: str
    id: str
    type: str
    title: str
    summary: str | None
    status: str
    snippet: str | None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _do_search(
    q: str,
    db: Session,
    *,
    project_id: str | None = None,
    type_filter: str | None = None,
    limit: int = 20,
) -> list[SearchResult]:
    """Run FTS query and return ranked results."""
    q = q.strip()
    if not q:
        return []

    # Build tsquery from user input — use plainto_tsquery for safety
    tsq = func.plainto_tsquery("english", q)

    stmt = (
        select(
            WorkItem,
            func.ts_rank(WorkItem.design_doc_search, tsq).label("rank"),
        )
        .where(WorkItem.design_doc_search.isnot(None))
        .where(WorkItem.design_doc_search.op("@@")(tsq))
        .order_by(text("rank DESC"))
        .limit(limit)
    )

    if project_id:
        stmt = stmt.where(WorkItem.project_id == project_id)

    if type_filter:
        for wt in WorkItemType:
            if wt.value.lower() == type_filter.lower():
                stmt = stmt.where(WorkItem.type == wt)
                break

    rows = db.execute(stmt).all()

    # Fetch project display names in bulk
    project_ids = {r.WorkItem.project_id for r in rows}
    project_names: dict[str, str] = {}
    if project_ids:
        projects = db.scalars(select(Project).where(Project.id.in_(project_ids))).all()
        project_names = {p.id: p.display_name for p in projects}

    results = []
    for row in rows:
        item = row.WorkItem
        results.append(
            SearchResult(
                project_id=item.project_id,
                project_name=project_names.get(item.project_id, item.project_id),
                id=item.id,
                type=item.type.value,
                title=item.title,
                summary=item.summary,
                status=item.status.value,
                snippet=(
                    item.summary
                    or (item.design_doc_content[:200] if item.design_doc_content else None)
                ),
            )
        )
    return results


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/api/search", response_class=HTMLResponse)
def global_search(
    request: Request,
    db: Session = Depends(get_db),
    q: str = "",
    project: str | None = None,
    type: str | None = None,  # noqa: A002
    limit: int = 20,
) -> Any:
    """Return an HTML fragment with search results (for htmx live search)."""
    limit = min(limit, _MAX_RESULTS)
    results = _do_search(q, db, project_id=project, type_filter=type, limit=limit)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/search_results.html",
        {"results": results, "query": q},
    )


@router.get("/project/{project_id}/search", response_class=HTMLResponse)
def project_search(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    q: str = "",
    type: str | None = None,  # noqa: A002
    page: int = 1,
) -> Any:
    """Full search page for a specific project."""
    from sqlalchemy import select as sa_select

    from orch.db.models import Project

    project = db.scalar(sa_select(Project).where(Project.id == project_id))
    limit = 20
    results = _do_search(q, db, project_id=project_id, type_filter=type, limit=limit + 1)
    has_more = len(results) > limit
    results = results[:limit]
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/search.html",
        {
            "current_project": project,
            "running_count": 0,
            "results": results,
            "query": q,
            "type_filter": type,
            "page": page,
            "has_more": has_more,
        },
    )
