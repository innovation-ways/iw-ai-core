"""Project-scoped pages: queue, history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import exists, select

from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchItem,
    BatchStatus,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/project/{project_id}")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return project


@dataclass
class QueueItem:
    id: str
    type: str
    title: str
    status: str
    created_at: datetime


_ACTIVE_BATCH_STATUSES = (
    BatchStatus.approved,
    BatchStatus.executing,
    BatchStatus.paused,
    BatchStatus.publishing,
)


def _queue_items(project_id: str, db: Session) -> tuple[list[QueueItem], list[QueueItem]]:
    """Return (approved_items, draft_items) for the queue page."""
    # Exclude items already associated with an active batch
    in_active_batch = (
        exists()
        .where(
            BatchItem.project_id == WorkItem.project_id,
            BatchItem.work_item_id == WorkItem.id,
        )
        .where(
            Batch.project_id == BatchItem.project_id,
            Batch.id == BatchItem.batch_id,
            Batch.status.in_(_ACTIVE_BATCH_STATUSES),
        )
        .correlate(WorkItem)
    )
    stmt = (
        select(WorkItem)
        .where(
            WorkItem.project_id == project_id,
            WorkItem.status.in_([WorkItemStatus.approved, WorkItemStatus.draft]),
            WorkItem.type != WorkItemType.Research,
            ~in_active_batch,
        )
        .order_by(WorkItem.created_at.desc())
    )
    rows = list(db.scalars(stmt))
    approved = [
        QueueItem(
            id=r.id,
            type=r.type.value,
            title=r.title,
            status=r.status.value,
            created_at=r.created_at,
        )
        for r in rows
        if r.status == WorkItemStatus.approved
    ]
    drafts = [
        QueueItem(
            id=r.id,
            type=r.type.value,
            title=r.title,
            status=r.status.value,
            created_at=r.created_at,
        )
        for r in rows
        if r.status == WorkItemStatus.draft
    ]
    return approved, drafts


@dataclass
class HistoryItem:
    id: str
    type: str
    title: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    duration_secs: int | None


_HISTORY_PAGE_SIZE = 20

_SORT_COLUMNS: dict[str, Any] = {
    "id": WorkItem.id,
    "title": WorkItem.title,
    "created_at": WorkItem.created_at,
    "type": WorkItem.type,
    "status": WorkItem.status,
}


def _history_items(
    project_id: str,
    db: Session,
    *,
    type_filter: str | None,
    status_filter: str | None,
    date_from: str | None,
    date_to: str | None,
    page: int = 1,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> tuple[list[HistoryItem], int]:
    """Return paginated, sorted history items and total count."""
    base = select(WorkItem).where(
        WorkItem.project_id == project_id,
        WorkItem.status.in_([WorkItemStatus.completed, WorkItemStatus.failed])
        | WorkItem.phase.in_([WorkItemPhase.done]),
    )

    if type_filter:
        for wt in WorkItemType:
            if wt.value.lower() == type_filter.lower():
                base = base.where(WorkItem.type == wt)
                break

    if status_filter:
        for ws in WorkItemStatus:
            if ws.value.lower() == status_filter.lower():
                base = base.where(WorkItem.status == ws)
                break

    if date_from:
        try:
            dt = datetime.fromisoformat(date_from).replace(tzinfo=UTC)
            base = base.where(WorkItem.created_at >= dt)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.fromisoformat(date_to).replace(tzinfo=UTC)
            base = base.where(WorkItem.created_at <= dt)
        except ValueError:
            pass

    # Total count (before pagination)
    from sqlalchemy import func as sa_func

    total = db.scalar(select(sa_func.count()).select_from(base.subquery())) or 0

    # Sorting — "duration" uses completed_at as proxy with NULLS LAST (asc) / NULLS FIRST (desc)
    if sort_by == "duration":
        if sort_dir == "asc":
            base = base.order_by(WorkItem.completed_at.asc().nulls_last())
        else:
            base = base.order_by(WorkItem.completed_at.desc().nulls_first())
    else:
        col = _SORT_COLUMNS.get(sort_by, WorkItem.created_at)
        direction = col.desc().nulls_last() if sort_dir == "desc" else col.asc().nulls_last()
        base = base.order_by(direction, WorkItem.id.desc() if sort_dir == "desc" else WorkItem.id.asc())

    # Pagination
    offset = (max(page, 1) - 1) * _HISTORY_PAGE_SIZE
    stmt = base.offset(offset).limit(_HISTORY_PAGE_SIZE)

    items = []
    for r in db.scalars(stmt):
        duration: int | None = None
        if r.completed_at and r.created_at:
            duration = int((r.completed_at - r.created_at).total_seconds())
        items.append(
            HistoryItem(
                id=r.id,
                type=r.type.value,
                title=r.title,
                status=r.status.value,
                created_at=r.created_at,
                completed_at=r.completed_at,
                duration_secs=duration,
            )
        )
    return items, total


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/queue", response_class=HTMLResponse)
def project_queue(project_id: str, request: Request, db: Session = Depends(get_db)) -> Any:
    project = _get_project_or_404(project_id, db)
    approved, drafts = _queue_items(project_id, db)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/queue.html",
        {
            "current_project": project,
            "running_count": 0,
            "approved_items": approved,
            "draft_items": drafts,
        },
    )


@router.get("/history", response_class=HTMLResponse)
def project_history(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    type: str | None = None,  # noqa: A002
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> Any:
    project = _get_project_or_404(project_id, db)
    items, total = _history_items(
        project_id,
        db,
        type_filter=type,
        status_filter=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/history.html",
        {
            "current_project": project,
            "running_count": 0,
            "items": items,
            "total": total,
            "type_filter": type,
            "status_filter": status,
            "date_from": date_from or "",
            "date_to": date_to or "",
            "item_types": [t.value for t in WorkItemType],
            "item_statuses": [s.value for s in [WorkItemStatus.completed, WorkItemStatus.failed]],
            "page": page,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
        },
    )
