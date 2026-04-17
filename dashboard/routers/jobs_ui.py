"""Jobs list and job detail pages — project-scoped routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from orch.db.models import Project
from orch.jobs.aggregator import JobsAggregator, JobType

if TYPE_CHECKING:
    from datetime import datetime

    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session


router = APIRouter(prefix="/project/{project_id}")


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project: Project | None = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")
    return project


@router.get("/jobs", response_class=HTMLResponse)
def jobs_page(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    type: list[str] = Query(default=None),  # noqa: A002
    status: list[str] = Query(default=None),
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
) -> Any:
    project = _get_project_or_404(project_id, db)

    filter_types: list[JobType] | None = None
    if type:
        filter_types = [JobType(t) for t in type]

    filter_statuses: list[str] | None = status

    parsed_date_from: datetime | None = None
    if date_from:
        try:
            import zoneinfo
            from datetime import datetime as dt

            parsed_date_from = dt.fromisoformat(date_from).replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        except ValueError:
            pass

    parsed_date_to: datetime | None = None
    if date_to:
        try:
            import zoneinfo
            from datetime import datetime as dt

            parsed_date_to = dt.fromisoformat(date_to).replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        except ValueError:
            pass

    aggregator = JobsAggregator(db)
    result = aggregator.list_jobs(
        project_id=project_id,
        types=filter_types,
        statuses=filter_statuses,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        page=page,
        page_size=25,
    )

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/jobs.html",
        {
            "current_project": project,
            "job_types": [t.value for t in JobType],
            "job_statuses": ["queued", "running", "completed", "failed", "paused", "cancelled"],
            "type_filter": type or [],
            "status_filter": status or [],
            "date_from": date_from or "",
            "date_to": date_to or "",
            "rows": result.rows,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
    )


@router.get("/jobs/fragment/table", response_class=HTMLResponse)
def jobs_fragment_table(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    type: list[str] = Query(default=None),  # noqa: A002
    status: list[str] = Query(default=None),
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
) -> Any:
    project = _get_project_or_404(project_id, db)

    filter_types: list[JobType] | None = None
    if type:
        filter_types = [JobType(t) for t in type]

    filter_statuses: list[str] | None = status

    parsed_date_from: datetime | None = None
    if date_from:
        try:
            import zoneinfo
            from datetime import datetime as dt

            parsed_date_from = dt.fromisoformat(date_from).replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        except ValueError:
            pass

    parsed_date_to: datetime | None = None
    if date_to:
        try:
            import zoneinfo
            from datetime import datetime as dt

            parsed_date_to = dt.fromisoformat(date_to).replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        except ValueError:
            pass

    aggregator = JobsAggregator(db)
    result = aggregator.list_jobs(
        project_id=project_id,
        types=filter_types,
        statuses=filter_statuses,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        page=page,
        page_size=25,
    )

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/jobs_table.html",
        {
            "current_project": project,
            "rows": result.rows,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "type_filter": type or [],
            "status_filter": status or [],
            "date_from": date_from or "",
            "date_to": date_to or "",
        },
    )


@router.get("/jobs/{job_type}/{job_id}", response_class=HTMLResponse)
def job_detail(
    project_id: str,
    job_type: str,
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)

    try:
        jt = JobType(job_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown job type: {job_type}") from None

    aggregator = JobsAggregator(db)
    job = aggregator.get_job(project_id=project_id, job_type=jt, job_id=job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/job_detail.html",
        {
            "current_project": _get_project_or_404(project_id, db),
            "job": job,
            "raw": job.raw,
        },
    )
