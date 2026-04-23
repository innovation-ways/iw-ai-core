"""Batch list and batch detail routes."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchItem,
    BatchStatus,
    DaemonEvent,
    Project,
    WorkflowStep,
    WorkItem,
)

if TYPE_CHECKING:
    from datetime import datetime

    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session


router = APIRouter(prefix="/project/{project_id}")

_ALL_STATUSES = [s.value for s in BatchStatus]
_HIDDEN_STATUSES = {"published", "publish_failed"}
_VISIBLE_STATUSES = [s for s in _ALL_STATUSES if s not in _HIDDEN_STATUSES]
_ACTIVE_STATUSES = [s for s in _VISIBLE_STATUSES if s not in ("archived", "cancelled")]


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class StepNode:
    """Minimal step info for the step_pipeline macro (strings, not enums)."""

    step_id: str
    agent_label: str
    status: str
    duration: str = ""


@dataclass
class BatchItemRow:
    """A work item inside a batch, with its step pipeline."""

    item_id: str
    title: str
    execution_group: int
    status: str
    steps: list[StepNode] = field(default_factory=list)
    duration_secs: float | None = None
    started_at: datetime | None = None
    started_at_ts: float | None = None
    ended_at_ts: float | None = None


@dataclass
class BatchRow:
    """A batch row for the list view."""

    id: str
    status: str
    total_items: int
    completed_items: int
    progress_pct: int
    created_at: datetime
    duration_secs: float | None


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")
    return project


def _get_batch_or_404(project_id: str, batch_id: str, db: Session) -> Batch:
    batch = db.scalar(
        select(Batch).where(
            Batch.project_id == project_id,
            Batch.id == batch_id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id!r} not found")
    return batch


def _format_duration(secs: float | None) -> str:
    if secs is None:
        return ""
    mins = int(secs // 60)
    s = int(secs % 60)
    return f"{mins}m{s:02d}s"


def _batch_item_rows(project_id: str, batch_id: str, db: Session) -> list[BatchItemRow]:
    """Load all BatchItems for a batch, enriched with work item + step data (C3 fix)."""
    from sqlalchemy import tuple_ as tuple_fn

    batch_items = list(
        db.scalars(
            select(BatchItem)
            .where(
                BatchItem.project_id == project_id,
                BatchItem.batch_id == batch_id,
            )
            .order_by(BatchItem.execution_group, BatchItem.work_item_id)
        ).all()
    )

    if not batch_items:
        return []

    work_item_keys = [(project_id, bi.work_item_id) for bi in batch_items]
    work_items = db.scalars(
        select(WorkItem).where(tuple_fn(WorkItem.project_id, WorkItem.id).in_(work_item_keys))
    ).all()
    work_item_map: dict[tuple[str, str], WorkItem] = {
        (wi.project_id, wi.id): wi for wi in work_items
    }

    steps = db.scalars(
        select(WorkflowStep)
        .where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id.in_([bi.work_item_id for bi in batch_items]),
        )
        .order_by(WorkflowStep.work_item_id, WorkflowStep.step_number)
    ).all()

    steps_map: dict[str, list[WorkflowStep]] = {}
    for s in steps:
        steps_map.setdefault(s.work_item_id, []).append(s)

    rows = []
    for bi in batch_items:
        wi = work_item_map.get((project_id, bi.work_item_id))
        title = wi.title if wi else bi.work_item_id

        item_steps = steps_map.get(bi.work_item_id, [])
        step_nodes = []
        for s in item_steps:
            dur = _format_duration(
                (s.completed_at - s.started_at).total_seconds()
                if s.started_at and s.completed_at
                else None
            )
            step_nodes.append(
                StepNode(
                    step_id=s.step_id,
                    agent_label=s.agent_label,
                    status=s.status.value,
                    duration=dur,
                )
            )

        dur_total: float | None = None
        if bi.started_at and bi.merged_at:
            dur_total = (bi.merged_at - bi.started_at).total_seconds()

        rows.append(
            BatchItemRow(
                item_id=bi.work_item_id,
                title=title,
                execution_group=bi.execution_group,
                status=bi.status.value,
                steps=step_nodes,
                duration_secs=dur_total,
                started_at=bi.started_at,
                started_at_ts=bi.started_at.timestamp() if bi.started_at else None,
                ended_at_ts=bi.merged_at.timestamp() if bi.merged_at else None,
            )
        )
    return rows


def _all_batches(project_id: str, db: Session, status_filter: list[str]) -> list[BatchRow]:
    stmt = select(Batch).where(Batch.project_id == project_id).order_by(Batch.created_at.desc())
    valid = [s for s in status_filter if s in _ALL_STATUSES]
    if valid:
        with contextlib.suppress(ValueError):
            stmt = stmt.where(Batch.status.in_([BatchStatus(s) for s in valid]))

    batches = list(db.scalars(stmt).all())
    rows = []
    for batch in batches:
        items = list(
            db.scalars(
                select(BatchItem).where(
                    BatchItem.project_id == project_id,
                    BatchItem.batch_id == batch.id,
                )
            ).all()
        )
        total = len(items)
        done = sum(1 for it in items if it.status.value in ("completed", "merged"))
        pct = int((done / total * 100) if total > 0 else 0)
        dur: float | None = None
        if batch.created_at and batch.completed_at:
            dur = (batch.completed_at - batch.created_at).total_seconds()
        rows.append(
            BatchRow(
                id=batch.id,
                status=batch.status.value,
                total_items=total,
                completed_items=done,
                progress_pct=pct,
                created_at=batch.created_at,
                duration_secs=dur,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/batches", response_class=HTMLResponse)
def batch_list(
    project_id: str,
    request: Request,
    status: list[str] = Query(default=[]),
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    batches = _all_batches(project_id, db, status_filter=status)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/batches.html",
        {
            "current_project": project,
            "running_count": 0,
            "batches": batches,
            "status_filter": status,
            "visible_statuses": _VISIBLE_STATUSES,
            "active_statuses": _ACTIVE_STATUSES,
        },
    )


@router.get("/batch/{batch_id}", response_class=HTMLResponse)
def batch_detail(
    project_id: str,
    batch_id: str,
    request: Request,
    tab: str = "items",
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    batch = _get_batch_or_404(project_id, batch_id, db)
    items = _batch_item_rows(project_id, batch_id, db)

    dur: float | None = None
    if batch.created_at and batch.completed_at:
        dur = (batch.completed_at - batch.created_at).total_seconds()

    # Render execution plan markdown to HTML if present
    plan_html: str | None = None
    if batch.execution_plan_md:
        import markdown as md

        plan_html = md.markdown(
            batch.execution_plan_md,
            extensions=["tables", "fenced_code"],
        )

    has_plan = batch.execution_plan_md is not None
    has_diagram = batch.execution_plan_png is not None

    # Compute gantt bounds for the timeline tab
    import datetime as _dt

    gantt_start_ts: float | None = None
    gantt_end_ts: float | None = None
    gantt_total_secs: float | None = None
    started_ts_list = [r.started_at_ts for r in items if r.started_at_ts is not None]
    ended_ts_list = [r.ended_at_ts for r in items if r.ended_at_ts is not None]
    if started_ts_list:
        gantt_start_ts = min(started_ts_list)
        if ended_ts_list:
            gantt_end_ts = max(ended_ts_list)
            # Extend to now if any item is still running
            if any(r.started_at_ts and not r.ended_at_ts for r in items):
                gantt_end_ts = max(gantt_end_ts, _dt.datetime.now(_dt.UTC).timestamp())
        else:
            gantt_end_ts = _dt.datetime.now(_dt.UTC).timestamp()
        gantt_total_secs = gantt_end_ts - gantt_start_ts if gantt_end_ts else None

    # Fetch dispatcher events for the logs tab
    batch_events: list[DaemonEvent] = []
    if tab == "logs":
        # Collect work item IDs belonging to this batch
        item_ids = [row.item_id for row in items]
        # Query events where entity_id is the batch itself or any of its items
        entity_ids = [batch_id, *item_ids]
        batch_events = list(
            db.scalars(
                select(DaemonEvent)
                .where(
                    DaemonEvent.project_id == project_id,
                    DaemonEvent.entity_id.in_(entity_ids),
                )
                .order_by(DaemonEvent.created_at.desc())
            ).all()
        )

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/batch_detail.html",
        {
            "current_project": project,
            "running_count": 0,
            "batch": batch,
            "batch_status": batch.status.value,
            "batch_duration_secs": dur,
            "items": items,
            "active_tab": tab,
            "plan_html": plan_html,
            "has_plan": has_plan,
            "has_diagram": has_diagram,
            "batch_events": batch_events,
            "gantt_start_ts": gantt_start_ts,
            "gantt_end_ts": gantt_end_ts,
            "gantt_total_secs": gantt_total_secs,
        },
    )


@router.get("/batches/fragment", response_class=HTMLResponse)
def batch_list_fragment(
    project_id: str,
    request: Request,
    status: list[str] = Query(default=[]),
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: returns only the batches tbody rows for live refresh."""
    _get_project_or_404(project_id, db)
    batches = _all_batches(project_id, db, status_filter=status)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/batches_table_rows.html",
        {
            "current_project": db.scalar(select(Project).where(Project.id == project_id)),
            "batches": batches,
            "status_filter": status,
        },
    )


@router.get("/batch/{batch_id}/fragment/items", response_class=HTMLResponse)
def batch_items_fragment(
    project_id: str,
    batch_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: returns only the batch items tbody rows for live refresh."""
    project = _get_project_or_404(project_id, db)
    _get_batch_or_404(project_id, batch_id, db)
    items = _batch_item_rows(project_id, batch_id, db)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/batch_items_rows.html",
        {
            "current_project": project,
            "items": items,
        },
    )


@router.get("/batch/{batch_id}/fragment/header", response_class=HTMLResponse)
def batch_detail_header_fragment(
    project_id: str,
    batch_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: returns batch detail header for live refresh."""
    project = _get_project_or_404(project_id, db)
    batch = _get_batch_or_404(project_id, batch_id, db)
    items = _batch_item_rows(project_id, batch_id, db)

    dur: float | None = None
    if batch.created_at and batch.completed_at:
        dur = (batch.completed_at - batch.created_at).total_seconds()

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/batch_detail_header.html",
        {
            "current_project": project,
            "batch": batch,
            "batch_status": batch.status.value,
            "batch_duration_secs": dur,
            "items": items,
        },
    )


@router.get("/batch/{batch_id}/diagram.png")
def batch_diagram_png(
    project_id: str,
    batch_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Serve the execution plan PNG image."""
    from fastapi.responses import Response as FastAPIResponse

    batch = _get_batch_or_404(project_id, batch_id, db)
    if batch.execution_plan_png is None:
        raise HTTPException(status_code=404, detail="No diagram available")
    return FastAPIResponse(
        content=batch.execution_plan_png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/batch/{batch_id}/diagram.drawio")
def batch_diagram_drawio(
    project_id: str,
    batch_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Download the draw.io XML file."""
    from fastapi.responses import Response as FastAPIResponse

    batch = _get_batch_or_404(project_id, batch_id, db)
    if batch.execution_plan_drawio is None:
        raise HTTPException(status_code=404, detail="No diagram available")
    return FastAPIResponse(
        content=batch.execution_plan_drawio,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{batch_id}-execution-plan.drawio"',
        },
    )
