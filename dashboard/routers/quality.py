"""Dashboard Quality Gates tab — launch and monitor static analysis runs per project."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.routers._run_helpers import (
    action_response,
    build_category_cards,
    build_run_rows,
    get_project_or_404,
    group_cards,
)
from orch.db.models import Project, TestRun, TestRunStatus
from orch.test_runner import kill_test_run, launch_test_run

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/project/{project_id}")

_RUN_TYPE = "quality"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_quality_config(project: Project) -> dict[str, Any]:
    """Extract quality_config from project JSONB config."""
    config: dict[str, Any] = project.config or {}
    result: dict[str, Any] = config.get("quality_config", {})
    return result


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@router.get("/quality", response_class=HTMLResponse)
def quality_page(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    tab: str = "launch",
) -> Any:
    project = get_project_or_404(project_id, db)
    quality_config = _get_quality_config(project)
    templates: Jinja2Templates = request.app.state.templates

    active_tab = tab if tab in ("launch", "runs") else "launch"

    context: dict[str, Any] = {
        "current_project": project,
        "running_count": 0,
        "active_tab": active_tab,
        "has_config": bool(quality_config.get("categories")),
    }

    if active_tab == "launch":
        cards = build_category_cards(project_id, quality_config, db, run_type=_RUN_TYPE)
        context["grouped_categories"] = group_cards(cards)
    elif active_tab == "runs":
        context["runs"] = build_run_rows(project_id, db, run_type=_RUN_TYPE)

    return templates.TemplateResponse(
        request,
        "pages/project/quality.html",
        context,
    )


# ---------------------------------------------------------------------------
# Fragment routes
# ---------------------------------------------------------------------------


@router.get("/quality/fragment/launch", response_class=HTMLResponse)
def quality_fragment_launch(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = get_project_or_404(project_id, db)
    quality_config = _get_quality_config(project)
    templates: Jinja2Templates = request.app.state.templates
    cards = build_category_cards(project_id, quality_config, db, run_type=_RUN_TYPE)
    return templates.TemplateResponse(
        request,
        "fragments/quality_launch.html",
        {
            "current_project": project,
            "grouped_categories": group_cards(cards),
            "has_config": bool(quality_config.get("categories")),
        },
    )


@router.get("/quality/fragment/runs", response_class=HTMLResponse)
def quality_fragment_runs(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = get_project_or_404(project_id, db)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/quality_runs.html",
        {
            "current_project": project,
            "runs": build_run_rows(project_id, db, run_type=_RUN_TYPE),
        },
    )


@router.get("/quality/fragment/log/{run_id}", response_class=HTMLResponse)
def quality_fragment_log(
    project_id: str,
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = get_project_or_404(project_id, db)
    run = db.scalar(select(TestRun).where(TestRun.id == run_id, TestRun.project_id == project_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Quality run not found")

    log_content = ""
    if run.log_path and Path(run.log_path).is_file():
        try:
            lines = Path(run.log_path).read_text(encoding="utf-8", errors="replace").splitlines()
            if len(lines) > 2000:
                log_content = f"... (showing last 2000 of {len(lines)} lines) ...\n"
                log_content += "\n".join(lines[-2000:])
            else:
                log_content = "\n".join(lines)
        except OSError:
            log_content = "(Error reading log file)"

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/tests_log.html",
        {
            "current_project": project,
            "run": run,
            "log_content": log_content,
            "is_running": run.status == TestRunStatus.running,
            "run_type_label": "Quality",
            "log_fetch_url": f"/project/{project_id}/quality/fragment/log/{run_id}",
        },
    )


# ---------------------------------------------------------------------------
# Action routes
# ---------------------------------------------------------------------------


@router.post("/api/quality/launch/{category}", response_class=Response)
def launch_quality_gate(
    project_id: str,
    category: str,
    db: Session = Depends(get_db),
) -> Any:
    project = get_project_or_404(project_id, db)
    quality_config = _get_quality_config(project)
    categories = quality_config.get("categories", {})

    if category not in categories:
        raise HTTPException(status_code=400, detail=f"Unknown quality category: {category}")

    # Check for already running/pending run in same category
    existing = db.scalar(
        select(TestRun).where(
            TestRun.project_id == project_id,
            TestRun.category == category,
            TestRun.run_type == _RUN_TYPE,
            TestRun.status.in_([TestRunStatus.pending, TestRunStatus.running]),
        )
    )
    if existing:
        return action_response(
            f"A {category} quality run is already in progress (#{existing.id}).",
            toast_type="warning",
        )

    cat_config = categories[category]
    command = cat_config["command"]

    run = TestRun(
        project_id=project_id,
        category=category,
        status=TestRunStatus.pending,
        command=command,
        triggered_by="user",
        run_type=_RUN_TYPE,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    thread = threading.Thread(
        target=launch_test_run,
        args=(run.id,),
        daemon=True,
        name=f"quality-run-{run.id}",
    )
    thread.start()

    return action_response(
        f"Quality run #{run.id} launched ({cat_config.get('label', category)}).", reload=True
    )


@router.post("/api/quality/kill/{run_id}", response_class=Response)
def kill_quality_gate(
    project_id: str,
    run_id: int,
    db: Session = Depends(get_db),
) -> Any:
    get_project_or_404(project_id, db)
    run = db.scalar(select(TestRun).where(TestRun.id == run_id, TestRun.project_id == project_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Quality run not found")

    success = kill_test_run(run_id)
    if success:
        return action_response(
            f"Quality run #{run_id} cancelled.", toast_type="warning", reload=True
        )
    return action_response(f"Quality run #{run_id} is not running.", toast_type="warning")
