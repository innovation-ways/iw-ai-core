"""Dashboard Tests tab — launch, monitor, and review test runs per project."""

from __future__ import annotations

import json
import logging
import mimetypes
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy import select

from dashboard.dependencies import get_db
from orch.db.models import Project, TestRun, TestRunStatus
from orch.test_runner import kill_test_run, launch_test_run

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/project/{project_id}")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return project


def _get_test_config(project: Project) -> dict[str, Any]:
    """Extract test_config from project JSONB config."""
    config = project.config or {}
    return config.get("test_config", {})


def _action_response(
    message: str,
    toast_type: str = "success",
    *,
    reload: bool = False,
) -> Response:
    """Return 204 with HX-Trigger header to show a toast."""
    toast: dict[str, Any] = {"message": message, "type": toast_type}
    if reload:
        toast["reload"] = True
    trigger = json.dumps({"showToast": toast})
    return Response(
        status_code=204,
        headers={
            "HX-Trigger": trigger,
            "HX-Refresh": "false",
        },
    )


@dataclass
class TestCategoryCard:
    key: str
    label: str
    description: str
    command: str
    last_run: TestRun | None = None


@dataclass
class TestRunRow:
    id: int
    category: str
    status: str
    command: str
    duration_secs: float | None
    started_at: datetime | None
    finished_at: datetime | None
    exit_code: int | None
    has_report: bool
    has_log: bool


@dataclass
class AllureSummary:
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    broken: int = 0
    duration_ms: int = 0
    run_id: int | None = None
    category: str = ""
    started_at: datetime | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any], run: TestRun) -> AllureSummary:
        stat = data.get("statistic", {})
        time_info = data.get("time", {})
        return cls(
            total=stat.get("total", 0),
            passed=stat.get("passed", 0),
            failed=stat.get("failed", 0),
            skipped=stat.get("skipped", 0),
            broken=stat.get("broken", 0),
            duration_ms=time_info.get("duration", 0),
            run_id=run.id,
            category=run.category,
            started_at=run.started_at,
        )


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@router.get("/tests", response_class=HTMLResponse)
def tests_page(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    tab: str = "launch",
) -> Any:
    project = _get_project_or_404(project_id, db)
    test_config = _get_test_config(project)
    templates: Jinja2Templates = request.app.state.templates

    active_tab = tab if tab in ("launch", "runs", "results") else "launch"

    # Build context based on active tab
    context: dict[str, Any] = {
        "current_project": project,
        "running_count": 0,
        "active_tab": active_tab,
        "test_config": test_config,
        "has_config": bool(test_config.get("categories")),
    }

    if active_tab == "launch":
        context["categories"] = _build_category_cards(project_id, test_config, db)
    elif active_tab == "runs":
        context["runs"] = _build_run_rows(project_id, db)
    elif active_tab == "results":
        context["summary"] = _get_latest_summary(project_id, db)
        context["recent_runs"] = _get_completed_runs(project_id, db, limit=20)

    return templates.TemplateResponse(
        request,
        "pages/project/tests.html",
        context,
    )


# ---------------------------------------------------------------------------
# Fragment routes
# ---------------------------------------------------------------------------


@router.get("/tests/fragment/launch", response_class=HTMLResponse)
def tests_fragment_launch(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    test_config = _get_test_config(project)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/tests_launch.html",
        {
            "current_project": project,
            "categories": _build_category_cards(project_id, test_config, db),
            "has_config": bool(test_config.get("categories")),
        },
    )


@router.get("/tests/fragment/runs", response_class=HTMLResponse)
def tests_fragment_runs(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/tests_runs.html",
        {
            "current_project": project,
            "runs": _build_run_rows(project_id, db),
        },
    )


@router.get("/tests/fragment/results", response_class=HTMLResponse)
def tests_fragment_results(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/tests_results.html",
        {
            "current_project": project,
            "summary": _get_latest_summary(project_id, db),
            "recent_runs": _get_completed_runs(project_id, db, limit=20),
        },
    )


@router.get("/tests/fragment/results/{run_id}", response_class=HTMLResponse)
def tests_fragment_results_for_run(
    project_id: str,
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    run = db.scalar(select(TestRun).where(TestRun.id == run_id, TestRun.project_id == project_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    summary = None
    if run.summary:
        summary = AllureSummary.from_json(run.summary, run)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/tests_results.html",
        {
            "current_project": project,
            "summary": summary,
            "recent_runs": _get_completed_runs(project_id, db, limit=20),
            "selected_run_id": run_id,
        },
    )


@router.get("/tests/fragment/log/{run_id}", response_class=HTMLResponse)
def tests_fragment_log(
    project_id: str,
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    run = db.scalar(select(TestRun).where(TestRun.id == run_id, TestRun.project_id == project_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    log_content = ""
    if run.log_path and Path(run.log_path).is_file():
        try:
            lines = Path(run.log_path).read_text(encoding="utf-8", errors="replace").splitlines()
            # Tail last 2000 lines for large logs
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
        },
    )


# ---------------------------------------------------------------------------
# Action routes
# ---------------------------------------------------------------------------


@router.post("/api/tests/launch/{category}", response_class=Response)
def launch_test(
    project_id: str,
    category: str,
    db: Session = Depends(get_db),
) -> Any:
    project = _get_project_or_404(project_id, db)
    test_config = _get_test_config(project)
    categories = test_config.get("categories", {})

    if category not in categories:
        raise HTTPException(status_code=400, detail=f"Unknown test category: {category}")

    # Check for already running/pending run in same category
    existing = db.scalar(
        select(TestRun).where(
            TestRun.project_id == project_id,
            TestRun.category == category,
            TestRun.status.in_([TestRunStatus.pending, TestRunStatus.running]),
        )
    )
    if existing:
        return _action_response(
            f"A {category} test run is already in progress (#{existing.id}).",
            toast_type="warning",
        )

    cat_config = categories[category]
    command = cat_config["command"]

    # Create test run row
    run = TestRun(
        project_id=project_id,
        category=category,
        status=TestRunStatus.pending,
        command=command,
        triggered_by="user",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Launch in background thread
    thread = threading.Thread(
        target=launch_test_run,
        args=(run.id,),
        daemon=True,
        name=f"test-run-{run.id}",
    )
    thread.start()

    return _action_response(
        f"Test run #{run.id} launched ({cat_config.get('label', category)}).", reload=True
    )


@router.post("/api/tests/kill/{run_id}", response_class=Response)
def kill_test(
    project_id: str,
    run_id: int,
    db: Session = Depends(get_db),
) -> Any:
    _get_project_or_404(project_id, db)
    run = db.scalar(select(TestRun).where(TestRun.id == run_id, TestRun.project_id == project_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    success = kill_test_run(run_id)
    if success:
        return _action_response(f"Test run #{run_id} cancelled.", toast_type="warning", reload=True)
    return _action_response(f"Test run #{run_id} is not running.", toast_type="warning")


# ---------------------------------------------------------------------------
# Report serving route
# ---------------------------------------------------------------------------


@router.get("/tests/report/{run_id}/{file_path:path}", response_class=Response)
def serve_allure_report(
    project_id: str,
    run_id: int,
    file_path: str,
    db: Session = Depends(get_db),
) -> Any:
    """Serve static files from the Allure report directory."""
    _get_project_or_404(project_id, db)
    run = db.scalar(select(TestRun).where(TestRun.id == run_id, TestRun.project_id == project_id))
    if run is None or not run.allure_report_dir:
        raise HTTPException(status_code=404, detail="Report not found")

    report_root = Path(run.allure_report_dir).resolve()
    if not file_path:
        file_path = "index.html"

    target = (report_root / file_path).resolve()

    # Security: ensure path doesn't escape report directory
    if not str(target).startswith(str(report_root)):
        raise HTTPException(status_code=403, detail="Path traversal blocked")

    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    content_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(
        path=str(target),
        media_type=content_type or "application/octet-stream",
    )


# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------


def _build_category_cards(
    project_id: str, test_config: dict[str, Any], db: Session
) -> list[TestCategoryCard]:
    """Build category cards with last run info."""
    categories = test_config.get("categories", {})
    cards = []
    for key, cat in categories.items():
        last_run = db.scalar(
            select(TestRun)
            .where(TestRun.project_id == project_id, TestRun.category == key)
            .order_by(TestRun.created_at.desc())
            .limit(1)
        )
        cards.append(
            TestCategoryCard(
                key=key,
                label=cat.get("label", key),
                description=cat.get("description", ""),
                command=cat.get("command", ""),
                last_run=last_run,
            )
        )
    return cards


def _build_run_rows(project_id: str, db: Session) -> list[TestRunRow]:
    """Build run rows for the runs table."""
    runs = list(
        db.scalars(
            select(TestRun)
            .where(TestRun.project_id == project_id)
            .order_by(TestRun.created_at.desc())
            .limit(50)
        )
    )
    return [
        TestRunRow(
            id=r.id,
            category=r.category,
            status=r.status.value,
            command=r.command,
            duration_secs=r.duration_secs,
            started_at=r.started_at,
            finished_at=r.finished_at,
            exit_code=r.exit_code,
            has_report=bool(r.allure_report_dir and Path(r.allure_report_dir).is_dir()),
            has_log=bool(r.log_path and Path(r.log_path).is_file()),
        )
        for r in runs
    ]


def _get_latest_summary(project_id: str, db: Session) -> AllureSummary | None:
    """Get the Allure summary from the most recent completed run."""
    run = db.scalar(
        select(TestRun)
        .where(
            TestRun.project_id == project_id,
            TestRun.status.in_([TestRunStatus.passed, TestRunStatus.failed]),
            TestRun.summary.isnot(None),
        )
        .order_by(TestRun.created_at.desc())
        .limit(1)
    )
    if run is None or run.summary is None:
        return None
    return AllureSummary.from_json(run.summary, run)


def _get_completed_runs(project_id: str, db: Session, *, limit: int = 20) -> list[TestRun]:
    """Get recent completed/failed runs for the run selector."""
    return list(
        db.scalars(
            select(TestRun)
            .where(
                TestRun.project_id == project_id,
                TestRun.status.in_([TestRunStatus.passed, TestRunStatus.failed]),
            )
            .order_by(TestRun.created_at.desc())
            .limit(limit)
        )
    )
