"""Project-scoped pages: queue, history, analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import exists, nulls_first, nulls_last, select

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

_HISTORY_PAGE_SIZE = 20

# Statuses that appear in history
_HISTORY_STATUSES = {WorkItemStatus.completed, WorkItemStatus.failed}
_HISTORY_PHASES = {WorkItemPhase.done}

# Sort columns mapping for _history_items()
_SORT_COLUMNS = {
    "id": WorkItem.id,
    "type": WorkItem.type,
    "title": WorkItem.title,
    "status": WorkItem.status,
    "created_at": WorkItem.created_at,
}
_ALLOWED_SORT_BY = {"id", "type", "title", "status", "created_at", "duration"}
_ALLOWED_SORT_DIR = ("asc", "desc")


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


def _history_items(
    project_id: str,
    db: Session,
    *,
    type_filter: str | None,
    status_filter: str | None,
    date_from: str | None,
    date_to: str | None,
    page: int,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> tuple[list[HistoryItem], int]:
    """Return (items_on_page, total_count) for the history page."""
    # Validate and normalize sort parameters
    if sort_by not in _ALLOWED_SORT_BY:
        sort_by = "created_at"
    if sort_dir not in _ALLOWED_SORT_DIR:
        sort_dir = "desc"

    stmt = select(WorkItem).where(
        WorkItem.project_id == project_id,
        WorkItem.status.in_([WorkItemStatus.completed, WorkItemStatus.failed])
        | WorkItem.phase.in_([WorkItemPhase.done]),
    )

    if type_filter:
        # match case-insensitively against enum value
        for wt in WorkItemType:
            if wt.value.lower() == type_filter.lower():
                stmt = stmt.where(WorkItem.type == wt)
                break

    if status_filter:
        for ws in WorkItemStatus:
            if ws.value.lower() == status_filter.lower():
                stmt = stmt.where(WorkItem.status == ws)
                break

    if date_from:
        try:
            dt = datetime.fromisoformat(date_from).replace(tzinfo=UTC)
            stmt = stmt.where(WorkItem.created_at >= dt)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.fromisoformat(date_to).replace(tzinfo=UTC)
            stmt = stmt.where(WorkItem.created_at <= dt)
        except ValueError:
            pass

    # Apply dynamic sorting
    if sort_by == "duration":
        if sort_dir == "asc":
            stmt = stmt.order_by(nulls_last(WorkItem.completed_at.asc()))
        else:
            stmt = stmt.order_by(nulls_first(WorkItem.completed_at.desc()))
    else:
        col = _SORT_COLUMNS[sort_by]
        stmt = stmt.order_by(col.asc()) if sort_dir == "asc" else stmt.order_by(col.desc())

    all_rows = list(db.scalars(stmt))
    total = len(all_rows)
    offset = (page - 1) * _HISTORY_PAGE_SIZE
    page_rows = all_rows[offset : offset + _HISTORY_PAGE_SIZE]

    items = []
    for r in page_rows:
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
    if page < 1:
        page = 1
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
    total_pages = max(1, (total + _HISTORY_PAGE_SIZE - 1) // _HISTORY_PAGE_SIZE)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/history.html",
        {
            "current_project": project,
            "running_count": 0,
            "items": items,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "page_size": _HISTORY_PAGE_SIZE,
            "type_filter": type,
            "status_filter": status,
            "date_from": date_from or "",
            "date_to": date_to or "",
            "item_types": [t.value for t in WorkItemType],
            "item_statuses": [s.value for s in [WorkItemStatus.completed, WorkItemStatus.failed]],
            "sort_by": sort_by,
            "sort_dir": sort_dir,
        },
    )


@router.get("/analytics", response_class=HTMLResponse)
def project_analytics(project_id: str, request: Request, db: Session = Depends(get_db)) -> Any:
    project = _get_project_or_404(project_id, db)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/analytics.html",
        {"current_project": project, "running_count": 0},
    )
