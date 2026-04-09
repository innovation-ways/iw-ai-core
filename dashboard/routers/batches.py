"""Batch list and batch detail routes."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchItem,
    BatchStatus,
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
    """Load all BatchItems for a batch, enriched with work item + step data."""
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

    rows = []
    for bi in batch_items:
        item = db.scalar(
            select(WorkItem).where(
                WorkItem.project_id == project_id,
                WorkItem.id == bi.work_item_id,
            )
        )
        title = item.title if item else bi.work_item_id

        steps = list(
            db.scalars(
                select(WorkflowStep)
                .where(
                    WorkflowStep.project_id == project_id,
                    WorkflowStep.work_item_id == bi.work_item_id,
                )
                .order_by(WorkflowStep.step_number)
            ).all()
        )
        step_nodes = []
        for s in steps:
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

        # Duration: sum of all completed steps
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
            )
        )
    return rows


def _all_batches(project_id: str, db: Session, status_filter: str | None) -> list[BatchRow]:
    stmt = select(Batch).where(Batch.project_id == project_id).order_by(Batch.created_at.desc())
    if status_filter and status_filter in _ALL_STATUSES:
        with contextlib.suppress(ValueError):
            stmt = stmt.where(Batch.status == BatchStatus(status_filter))

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
    status: str | None = None,
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
            "all_statuses": _ALL_STATUSES,
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
        headers={"Cache-Control": "public, max-age=3600"},
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
