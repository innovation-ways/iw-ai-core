"""Work item detail page and htmx tab fragment routes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.utils.markdown import render_markdown
from orch.db.models import (
    BatchItem,
    BatchItemStatus,
    FixCycle,
    Project,
    StepRun,
    WorkflowStep,
    WorkItem,
)

if TYPE_CHECKING:
    from datetime import datetime

    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session


router = APIRouter(prefix="/project/{project_id}")


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class StepDetail:
    """Full step info for the item overview tab."""

    step_id: str
    agent_label: str
    step_type: str
    status: str
    duration_secs: float | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    run_count: int
    report_content: str | None = None


@dataclass
class ReportSection:
    """A rendered report for a single step, used in the reports tab."""

    step_id: str
    agent_label: str
    step_type: str
    status: str
    run_count: int
    report_html: str


@dataclass
class ArtifactFile:
    """A file in the artifact browser."""

    name: str
    path: str
    size_bytes: int
    is_dir: bool = False


@dataclass
class ItemMetrics:
    """Computed metrics for the item detail header."""

    total_duration_secs: float | None
    fix_cycles_count: int
    steps_completed: int
    steps_total: int


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")
    return project


def _get_item_or_404(project_id: str, item_id: str, db: Session) -> WorkItem:
    item = db.scalar(
        select(WorkItem).where(
            WorkItem.project_id == project_id,
            WorkItem.id == item_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail=f"Work item {item_id!r} not found")
    return item


def _get_steps(project_id: str, item_id: str, db: Session) -> list[StepDetail]:
    steps = list(
        db.scalars(
            select(WorkflowStep)
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
            .order_by(WorkflowStep.step_number)
        ).all()
    )
    result = []
    for step in steps:
        # Get run count and last error from step_runs
        runs = list(
            db.scalars(
                select(StepRun)
                .where(StepRun.step_id == step.id)
                .order_by(StepRun.run_number.desc())
            ).all()
        )
        last_run = runs[0] if runs else None
        error_msg = last_run.error_message if last_run else None

        dur: float | None = None
        if step.started_at and step.completed_at:
            dur = (step.completed_at - step.started_at).total_seconds()

        result.append(
            StepDetail(
                step_id=step.step_id,
                agent_label=step.agent_label,
                step_type=step.step_type.value,
                status=step.status.value,
                duration_secs=dur,
                started_at=step.started_at,
                completed_at=step.completed_at,
                error_message=error_msg,
                run_count=len(runs),
                report_content=step.report_content,
            )
        )
    return result


def _get_metrics(
    project_id: str, item_id: str, steps: list[StepDetail], db: Session
) -> ItemMetrics:
    # Total duration: from first step start to last step end
    started_ats = [s.started_at for s in steps if s.started_at]
    completed_ats = [s.completed_at for s in steps if s.completed_at]
    total_dur: float | None = None
    if started_ats and completed_ats:
        total_dur = (max(completed_ats) - min(started_ats)).total_seconds()

    # Fix cycles: sum across all steps
    step_db_ids = list(
        db.scalars(
            select(WorkflowStep.id).where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
        ).all()
    )
    fix_count = 0
    if step_db_ids:
        fix_count = len(
            list(db.scalars(select(FixCycle.id).where(FixCycle.step_id.in_(step_db_ids))).all())
        )

    steps_completed = sum(1 for s in steps if s.status == "completed")
    return ItemMetrics(
        total_duration_secs=total_dur,
        fix_cycles_count=fix_count,
        steps_completed=steps_completed,
        steps_total=len(steps),
    )


def _get_batch_ref(project_id: str, item_id: str, db: Session) -> str | None:
    bi = db.scalar(
        select(BatchItem).where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
        )
    )
    return bi.batch_id if bi else None


def _get_batch_item_error(project_id: str, item_id: str, db: Session) -> str | None:
    """Return the batch_item notes if the item failed at setup (no step runs)."""
    bi = db.scalar(
        select(BatchItem).where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
            BatchItem.status == BatchItemStatus.failed,
        )
    )
    if bi and bi.notes:
        return bi.notes
    return None


def _list_artifacts(_project_id: str, item: WorkItem, project: Project) -> list[ArtifactFile]:
    """Try to list artifact files from disk. Returns empty list on any error."""
    if item.design_doc_path is None:
        return []
    # Active items: look in the project repo
    # The design_doc_path is relative to repo_root, typically ai-dev/design/active/{id}/
    active_dir = Path(project.repo_root) / "ai-dev" / "design" / "active" / item.id
    if not active_dir.exists():
        return []
    files = []
    try:
        for entry in sorted(active_dir.iterdir()):
            files.append(
                ArtifactFile(
                    name=entry.name,
                    path=str(entry),
                    size_bytes=entry.stat().st_size if entry.is_file() else 0,
                    is_dir=entry.is_dir(),
                )
            )
    except OSError:
        pass
    return files


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/item/{item_id}", response_class=HTMLResponse)
def item_detail(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    steps = _get_steps(project_id, item_id, db)
    metrics = _get_metrics(project_id, item_id, steps, db)
    batch_ref = _get_batch_ref(project_id, item_id, db)
    setup_error = _get_batch_item_error(project_id, item_id, db)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/item_detail.html",
        {
            "current_project": project,
            "running_count": 0,
            "item": item,
            "item_type": item.type.value,
            "item_status": item.status.value,
            "steps": steps,
            "metrics": metrics,
            "batch_ref": batch_ref,
            "setup_error": setup_error,
        },
    )


@router.get("/item/{item_id}/tab/overview", response_class=HTMLResponse)
def item_tab_overview(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    steps = _get_steps(project_id, item_id, db)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_overview.html",
        {
            "current_project": project,
            "item": item,
            "steps": steps,
        },
    )


@router.get("/item/{item_id}/tab/design-doc", response_class=HTMLResponse)
def item_tab_design_doc(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)

    # Prefer archived Tier 1 content; fall back to reading from disk
    content: str | None = item.design_doc_content
    if content is None and item.design_doc_path and project.repo_root:
        disk_path = Path(project.repo_root) / item.design_doc_path
        try:
            content = disk_path.read_text(encoding="utf-8")
        except OSError:
            content = None

    design_doc_html = render_markdown(content)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_design_doc.html",
        {
            "item": item,
            "design_doc_html": design_doc_html,
            "has_content": bool(content),
        },
    )


@router.get("/item/{item_id}/tab/reports", response_class=HTMLResponse)
def item_tab_reports(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    steps = _get_steps(project_id, item_id, db)

    report_sections = [
        ReportSection(
            step_id=s.step_id,
            agent_label=s.agent_label,
            step_type=s.step_type,
            status=s.status,
            run_count=s.run_count,
            report_html=render_markdown(s.report_content),
        )
        for s in steps
        if s.report_content
    ]

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_reports.html",
        {
            "item": item,
            "report_sections": report_sections,
        },
    )


@router.get("/item/{item_id}/tab/artifacts", response_class=HTMLResponse)
def item_tab_artifacts(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    artifact_files = _list_artifacts(project_id, item, project)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_artifacts.html",
        {
            "item": item,
            "artifact_files": artifact_files,
            "is_archived": item.archived_at is not None,
            "archive_size_bytes": item.archive_size_bytes,
        },
    )
