"""Dashboard OSS compliance tab — scan, prepare, publish, and install jobs."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.routers._run_helpers import get_project_or_404
from orch.db.models import ProjectOssJob, ProjectOssJobKind, ProjectOssJobStatus
from orch.oss.config_writer import write_project_config

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/project/{project_id}")


def _running_job_of_kind(
    db: Session, project_id: str, kind: ProjectOssJobKind
) -> ProjectOssJob | None:
    return db.scalar(
        select(ProjectOssJob).where(
            ProjectOssJob.project_id == project_id,
            ProjectOssJob.kind == kind,
            ProjectOssJob.status.in_([ProjectOssJobStatus.queued, ProjectOssJobStatus.running]),
        )
    )


async def _stream_job_events(request: Request, job_id: int) -> AsyncGenerator[str, None]:
    from dashboard.services.oss_service import job_event_stream

    # Tests may set `app.state.oss_session_factory` to bind to a testcontainer
    # engine; in production we fall back to the live SessionLocal.
    factory = getattr(request.app.state, "oss_session_factory", None)
    if factory is None:
        from orch.db.session import SessionLocal

        factory = SessionLocal

    async for line in job_event_stream(factory, job_id):
        if await request.is_disconnected():
            break
        yield line


@router.get("/oss", response_class=HTMLResponse)
def oss_page(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = get_project_or_404(project_id, db)
    templates: Jinja2Templates = request.app.state.templates

    recent_jobs = list(
        db.scalars(
            select(ProjectOssJob)
            .where(ProjectOssJob.project_id == project_id)
            .order_by(ProjectOssJob.created_at.desc())
            .limit(20)
        )
    )

    from dashboard.services.oss_service import latest_scan, scan_summary

    latest = latest_scan(db, project_id)
    summary = scan_summary(db, project_id)

    findings_by_domain: dict[str, dict[str, Any]] = {}
    if latest:
        from collections import defaultdict

        by_domain: dict[str, list[Any]] = defaultdict(list)
        for f in latest.findings:
            by_domain[f.domain].append(f)
        for domain, findings in by_domain.items():
            must = sum(1 for f in findings if f.severity.value == "MUST")
            should = sum(1 for f in findings if f.severity.value == "SHOULD")
            info = sum(1 for f in findings if f.severity.value == "INFO")
            pass_status = sum(1 for f in findings if f.status.value == "pass")
            findings_by_domain[domain] = {
                "findings": findings,
                "counts": {
                    "must": must,
                    "should": should,
                    "info": info,
                    "pass_status": pass_status,
                    "total": len(findings),
                },
            }

    return templates.TemplateResponse(
        request,
        "pages/project/oss.html",
        {
            "current_project": project,
            "recent_jobs": recent_jobs,
            "oss_enabled": project.oss_enabled,
            "scan_summary": summary,
            "findings_by_domain": findings_by_domain,
        },
    )


@router.get("/oss/status", response_class=HTMLResponse)
def oss_status_frame(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = get_project_or_404(project_id, db)
    templates: Jinja2Templates = request.app.state.templates

    from dashboard.services.oss_service import scan_summary

    summary = scan_summary(db, project_id)

    running_job = db.scalar(
        select(ProjectOssJob)
        .where(
            ProjectOssJob.project_id == project_id,
            ProjectOssJob.status.in_([ProjectOssJobStatus.queued, ProjectOssJobStatus.running]),
        )
        .order_by(ProjectOssJob.created_at.desc())
        .limit(1)
    )

    return templates.TemplateResponse(
        request,
        "fragments/oss_status_frame.html",
        {
            "current_project": project,
            "oss_enabled": project.oss_enabled,
            "scan_summary": summary,
            "running_job": running_job,
        },
    )


@router.get("/oss/tools", response_class=HTMLResponse)
def oss_tools(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    get_project_or_404(project_id, db)
    templates: Jinja2Templates = request.app.state.templates

    from dashboard.services.oss_service import probe_tier1_dashboard

    tools = probe_tier1_dashboard()
    all_installed = all(info["installed"] for info in tools.values())

    return templates.TemplateResponse(
        request,
        "fragments/oss_install_modal.html",
        {
            "project_id": project_id,
            "tools": tools,
            "all_installed": all_installed,
        },
    )


@router.post("/oss/install", response_class=Response)
def oss_install(
    project_id: str,
    db: Session = Depends(get_db),
) -> Any:
    get_project_or_404(project_id, db)

    existing = _running_job_of_kind(db, project_id, ProjectOssJobKind.install)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Install job #{existing.id} is already running",
        )

    from dashboard.services.oss_service import enqueue_job

    job = enqueue_job(db, project_id, ProjectOssJobKind.install)
    db.commit()
    db.refresh(job)

    thread = threading.Thread(
        target=lambda: asyncio.run(_run_oss_job(job.id)),
        daemon=True,
        name=f"oss-install-{job.id}",
    )
    thread.start()

    toast = json.dumps({"showToast": {"message": f"Install job #{job.id} started", "type": "info"}})
    stream_url = f"/project/{project_id}/oss/stream/{job.id}"
    return Response(
        status_code=200,
        content=json.dumps({"job_id": job.id, "stream_url": stream_url}),
        media_type="application/json",
        headers={"HX-Trigger": toast},
    )


@router.post("/oss/enable", response_class=Response)
def oss_enable(
    project_id: str,
    db: Session = Depends(get_db),
) -> Any:
    project = get_project_or_404(project_id, db)

    write_project_config(project, force=True)  # type: ignore[arg-type]

    project.oss_enabled = True
    db.commit()

    trigger = json.dumps(
        {
            "showToast": {"message": "OSS compliance enabled", "type": "success"},
            "reload": True,
        }
    )
    return Response(
        status_code=204,
        headers={"HX-Trigger": trigger, "HX-Refresh": "false"},
    )


@router.post("/oss/disable", response_class=Response)
def oss_disable(
    project_id: str,
    db: Session = Depends(get_db),
) -> Any:
    project = get_project_or_404(project_id, db)

    project.oss_enabled = False
    db.commit()

    trigger = json.dumps(
        {
            "showToast": {"message": "OSS compliance disabled", "type": "info"},
            "reload": True,
        }
    )
    return Response(
        status_code=204,
        headers={"HX-Trigger": trigger, "HX-Refresh": "false"},
    )


@router.post("/oss/scan", response_class=Response)
def oss_scan(
    project_id: str,
    db: Session = Depends(get_db),
) -> Any:
    get_project_or_404(project_id, db)

    existing = _running_job_of_kind(db, project_id, ProjectOssJobKind.scan)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Scan job #{existing.id} is already running",
        )

    from dashboard.services.oss_service import enqueue_job

    job = enqueue_job(db, project_id, ProjectOssJobKind.scan)
    db.commit()
    db.refresh(job)

    thread = threading.Thread(
        target=lambda: asyncio.run(_run_oss_job(job.id)),
        daemon=True,
        name=f"oss-scan-{job.id}",
    )
    thread.start()

    stream_url = f"/project/{project_id}/oss/stream/{job.id}"
    return Response(
        status_code=200,
        content=json.dumps({"job_id": job.id, "stream_url": stream_url}),
        media_type="application/json",
    )


@router.post("/oss/prepare", response_class=Response)
def oss_prepare(
    project_id: str,
    db: Session = Depends(get_db),
) -> Any:
    get_project_or_404(project_id, db)

    existing = _running_job_of_kind(db, project_id, ProjectOssJobKind.prepare)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Prepare job #{existing.id} is already running",
        )

    from dashboard.services.oss_service import enqueue_job

    job = enqueue_job(db, project_id, ProjectOssJobKind.prepare)
    db.commit()
    db.refresh(job)

    thread = threading.Thread(
        target=lambda: asyncio.run(_run_oss_job(job.id)),
        daemon=True,
        name=f"oss-prepare-{job.id}",
    )
    thread.start()

    stream_url = f"/project/{project_id}/oss/stream/{job.id}"
    return Response(
        status_code=200,
        content=json.dumps({"job_id": job.id, "stream_url": stream_url}),
        media_type="application/json",
    )


@router.post("/oss/publish", response_class=Response)
def oss_publish(
    project_id: str,
    db: Session = Depends(get_db),
) -> Any:
    get_project_or_404(project_id, db)

    existing = _running_job_of_kind(db, project_id, ProjectOssJobKind.publish)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Publish job #{existing.id} is already running",
        )

    from dashboard.services.oss_service import enqueue_job

    job = enqueue_job(db, project_id, ProjectOssJobKind.publish)
    db.commit()
    db.refresh(job)

    thread = threading.Thread(
        target=lambda: asyncio.run(_run_oss_job(job.id)),
        daemon=True,
        name=f"oss-publish-{job.id}",
    )
    thread.start()

    stream_url = f"/project/{project_id}/oss/stream/{job.id}"
    return Response(
        status_code=200,
        content=json.dumps({"job_id": job.id, "stream_url": stream_url}),
        media_type="application/json",
    )


@router.get("/oss/stream/{job_id}", response_class=StreamingResponse)
async def oss_stream(
    project_id: str,
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    get_project_or_404(project_id, db)

    job = db.scalar(
        select(ProjectOssJob).where(
            ProjectOssJob.id == job_id,
            ProjectOssJob.project_id == project_id,
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return StreamingResponse(
        _stream_job_events(request, job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _run_oss_job(job_id: int) -> None:
    from dashboard.services.oss_service import run_job
    from orch.db.session import SessionLocal

    await run_job(lambda: SessionLocal(), job_id)
