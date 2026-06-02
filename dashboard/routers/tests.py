"""Dashboard Tests tab — launch, monitor, and review test runs per project."""

from __future__ import annotations

import logging
import mimetypes
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.routers._run_helpers import (
    action_response,
    build_category_cards,
    build_run_rows,
    get_project_or_404,
    group_cards,
)
from dashboard.routers._test_health_helpers import build_test_health_cards
from orch.db.models import Project, TestRun, TestRunStatus
from orch.test_health_service import latest
from orch.test_runner import kill_test_run, launch_test_run

if TYPE_CHECKING:
    from datetime import datetime

    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/project/{project_id}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_test_config(project: Project) -> dict[str, Any]:
    """Extract test_config from project JSONB config."""
    config: dict[str, Any] = project.config or {}
    result: dict[str, Any] = config.get("test_config", {})
    return result


@dataclass
class AllureSummary:
    """Parsed summary statistics from an Allure report JSON.

    Attributes:
        total: Total test count.
        passed: Count of passed tests.
        failed: Count of failed tests.
        skipped: Count of skipped tests.
        broken: Count of broken tests.
        duration_ms: Total duration in milliseconds.
        run_id: TestRun primary key, or None.
        category: Test category key.
        started_at: When the run started, or None.
    """

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
        """Construct an AllureSummary from a parsed allure-report summary.json dict.

        Args:
            data: Parsed contents of the Allure summary.json file.
            run: The TestRun row whose metadata is merged in.

        Returns:
            AllureSummary populated from both the JSON and the run row.
        """
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
    run: int | None = None,
) -> Any:
    """Render the Tests page with launch, runs, or results tab.

    Args:
        project_id: The project whose test config is used.
        request: The current FastAPI request.
        db: Active database session.
        tab: Active tab — 'launch', 'runs', or 'results'.
        run: Optional run ID to pre-select on the results tab.

    Returns:
        Full HTML tests page for the requested tab.
    """
    project = get_project_or_404(project_id, db)
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
        cards = build_category_cards(project_id, test_config, db, run_type="test")
        context["grouped_categories"] = group_cards(cards)
    elif active_tab == "runs":
        context["runs"] = build_run_rows(project_id, db, run_type="test")
    elif active_tab == "results":
        context.update(_build_results_context(project_id, run, db))

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
    """Return the test launch panel fragment for htmx partial updates.

    Args:
        project_id: The project whose test categories are rendered.
        request: The current FastAPI request.
        db: Active database session.

    Returns:
        HTML fragment with test category cards.
    """
    project = get_project_or_404(project_id, db)
    test_config = _get_test_config(project)
    templates: Jinja2Templates = request.app.state.templates
    cards = build_category_cards(project_id, test_config, db, run_type="test")
    return templates.TemplateResponse(
        request,
        "fragments/tests_launch.html",
        {
            "current_project": project,
            "grouped_categories": group_cards(cards),
            "has_config": bool(test_config.get("categories")),
        },
    )


@router.get("/tests/fragment/runs", response_class=HTMLResponse)
def tests_fragment_runs(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Return the test runs history fragment.

    Args:
        project_id: The project whose test run history is shown.
        request: The current FastAPI request.
        db: Active database session.

    Returns:
        HTML fragment with recent test run rows.
    """
    project = get_project_or_404(project_id, db)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/tests_runs.html",
        {
            "current_project": project,
            "runs": build_run_rows(project_id, db, run_type="test"),
        },
    )


@router.get("/tests/fragment/results", response_class=HTMLResponse)
def tests_fragment_results(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    run: int | None = None,
) -> Any:
    """Return the results tab fragment, optionally for a specific run.

    Args:
        project_id: The project whose test results are shown.
        request: The current FastAPI request.
        db: Active database session.
        run: Optional run ID to pre-select; defaults to most recent completed run.

    Returns:
        HTML fragment with the results view and run selector.
    """
    project = get_project_or_404(project_id, db)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/tests_results.html",
        {"current_project": project, **_build_results_context(project_id, run, db)},
    )


@router.get("/tests/fragment/results/{run_id}", response_class=HTMLResponse)
def tests_fragment_results_for_run(
    project_id: str,
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Return the results fragment pre-selected to a specific run.

    Args:
        project_id: The project that owns the run.
        run_id: Database primary key of the TestRun to display.
        request: The current FastAPI request.
        db: Active database session.

    Returns:
        HTML fragment with results for the given run.
    """
    project = get_project_or_404(project_id, db)
    run = db.scalar(select(TestRun).where(TestRun.id == run_id, TestRun.project_id == project_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/tests_results.html",
        {"current_project": project, **_build_results_context(project_id, run_id, db)},
    )


@router.get("/test-health", response_class=HTMLResponse, operation_id="test_health_fragment_tests")
def test_health_fragment(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: Test Health panel with metric cards + SVG sparklines."""
    project = get_project_or_404(project_id, db)
    templates: Jinja2Templates = request.app.state.templates

    latest_snapshots = latest(db, project_id)
    metrics_data = build_test_health_cards(project, latest_snapshots, db)

    return templates.TemplateResponse(
        request,
        "fragments/test_health_panel.html",
        {
            "current_project": project,
            "metrics_data": metrics_data,
        },
    )


@router.get("/tests/fragment/log/{run_id}", response_class=HTMLResponse)
def tests_fragment_log(
    project_id: str,
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Return the log viewer fragment for a test run.

    Args:
        project_id: The project that owns the test run.
        run_id: Database primary key of the TestRun row.
        request: The current FastAPI request.
        db: Active database session.

    Returns:
        HTML fragment with the last 2000 lines of the run log (newest first).
    """
    project = get_project_or_404(project_id, db)
    run = db.scalar(select(TestRun).where(TestRun.id == run_id, TestRun.project_id == project_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    log_content = ""
    if run.log_path and Path(run.log_path).is_file():
        try:
            lines = Path(run.log_path).read_text(encoding="utf-8", errors="replace").splitlines()
            # Tail last 2000 lines for large logs, then reverse (newest first)
            if len(lines) > 2000:
                tail = lines[-2000:]
                tail.reverse()
                log_content = "\n".join(tail)
                log_content += f"\n\n... ({len(lines) - 2000} earlier lines not shown) ..."
            else:
                lines_copy = list(lines)
                lines_copy.reverse()
                log_content = "\n".join(lines_copy)
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
            "run_type_label": "Test",
            "log_fetch_url": f"/project/{project_id}/tests/fragment/log/{run_id}",
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
    """Launch a test run for the named category.

    Guards against concurrent E2E stack tests that share host ports.
    Returns a warning toast if a run is already active for this category.

    Args:
        project_id: The project to run tests for.
        category: Test category key from the project's test_config.
        db: Active database session.

    Returns:
        204 response with HX-Trigger toast; reloads on success.
    """
    project = get_project_or_404(project_id, db)
    test_config = _get_test_config(project)
    categories = test_config.get("categories", {})

    if category not in categories:
        raise HTTPException(status_code=400, detail=f"Unknown test category: {category}")

    # Check for already running/pending run in same category
    existing = db.scalar(
        select(TestRun).where(
            TestRun.project_id == project_id,
            TestRun.category == category,
            TestRun.run_type == "test",
            TestRun.status.in_([TestRunStatus.pending, TestRunStatus.running]),
        )
    )
    if existing:
        return action_response(
            f"A {category} test run is already in progress (#{existing.id}).",
            toast_type="warning",
        )

    cat_config = categories[category]
    command = cat_config["command"]

    # If this category uses the E2E docker stack, block concurrent stack launches.
    # All e2e_stack categories share the same ports — running two simultaneously
    # causes "port already allocated" Docker errors.
    if cat_config.get("e2e_stack"):
        blocking = _find_running_e2e_stack_test(project_id, category, categories, db)
        if blocking:
            return action_response(
                f"E2E stack already in use by run #{blocking.id} ({blocking.category}). "
                "Wait for it to finish before launching another E2E stack test.",
                toast_type="warning",
            )

    # Create test run row
    run = TestRun(
        project_id=project_id,
        category=category,
        status=TestRunStatus.pending,
        command=command,
        triggered_by="user",
        run_type="test",
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

    return action_response(
        f"Test run #{run.id} launched ({cat_config.get('label', category)}).", reload=True
    )


@router.post("/api/tests/kill/{run_id}", response_class=Response)
def kill_test(
    project_id: str,
    run_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Kill a running test run.

    Args:
        project_id: The project that owns the run.
        run_id: Database primary key of the TestRun to kill.
        db: Active database session.

    Returns:
        204 response with a toast indicating success or that the run was not active.
    """
    get_project_or_404(project_id, db)
    run = db.scalar(select(TestRun).where(TestRun.id == run_id, TestRun.project_id == project_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    success = kill_test_run(run_id)
    if success:
        return action_response(f"Test run #{run_id} cancelled.", toast_type="warning", reload=True)
    return action_response(f"Test run #{run_id} is not running.", toast_type="warning")


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
    get_project_or_404(project_id, db)
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
# Internal helpers
# ---------------------------------------------------------------------------


def _find_running_e2e_stack_test(
    project_id: str,
    current_category: str,
    categories: dict[str, Any],
    db: Session,
) -> TestRun | None:
    """Return any running/pending test that uses the shared E2E docker stack.

    E2E stack categories bind to fixed host ports — only one can run at a time.
    Checks all categories with e2e_stack=true except the one being launched.
    """
    e2e_stack_cats = [
        cat for cat, cfg in categories.items() if cfg.get("e2e_stack") and cat != current_category
    ]
    if not e2e_stack_cats:
        return None
    return db.scalar(
        select(TestRun).where(
            TestRun.project_id == project_id,
            TestRun.category.in_(e2e_stack_cats),
            TestRun.run_type == "test",
            TestRun.status.in_([TestRunStatus.pending, TestRunStatus.running]),
        )
    )


# ---------------------------------------------------------------------------
# Data builders (Allure-specific — tests only)
# ---------------------------------------------------------------------------


def _build_results_context(project_id: str, run_id: int | None, db: Session) -> dict[str, Any]:
    """Build the template context for the Results tab.

    Resolves the *selected* run (by ``run_id`` if given, else the most recent
    completed run) and renders the view around that run — its Allure report
    link and (when available) its parsed summary stats. Parsed summary stats
    are absent for most categories, but every completed run still has its own
    ``allure_report_dir``; the report link must therefore follow the selected
    run, NOT the latest run that happens to carry parsed stats (the I-?? bug:
    the report and summary were pinned to the newest summarised run regardless
    of the dropdown selection).
    """
    selected_run = _resolve_results_run(project_id, run_id, db)
    summary = (
        AllureSummary.from_json(selected_run.summary, selected_run)
        if selected_run is not None and selected_run.summary
        else None
    )
    context: dict[str, Any] = {
        "selected_run": selected_run,
        "summary": summary,
        "report_available": _report_available(selected_run),
        "recent_runs": _get_completed_runs(project_id, db, limit=20),
    }
    if selected_run is not None:
        context["selected_run_id"] = selected_run.id
    return context


def _report_available(run: TestRun | None) -> bool:
    """True when the run's Allure HTML report actually exists on disk.

    ``allure_report_dir`` is recorded for nearly every run, but the generated
    HTML is not always persisted (e.g. allure-generate failed, or the report
    was pruned). Gating the "Open Full Allure Report" link on the real
    ``index.html`` avoids linking to a 404 — matching what ``serve_allure_report``
    will actually serve.
    """
    if run is None or not run.allure_report_dir:
        return False
    return (Path(run.allure_report_dir) / "index.html").is_file()


def _resolve_results_run(project_id: str, run_id: int | None, db: Session) -> TestRun | None:
    """Return the run to display on the Results tab.

    When ``run_id`` names a real test run for this project, that run is used
    (whether or not it carries parsed summary stats). Otherwise fall back to
    the most recent completed run so the dropdown defaults to the newest entry.
    """
    if run_id is not None:
        run = db.scalar(
            select(TestRun).where(
                TestRun.id == run_id,
                TestRun.project_id == project_id,
                TestRun.run_type == "test",
            )
        )
        if run is not None:
            return run
    return db.scalar(
        select(TestRun)
        .where(
            TestRun.project_id == project_id,
            TestRun.run_type == "test",
            TestRun.status.in_([TestRunStatus.passed, TestRunStatus.failed]),
        )
        .order_by(TestRun.created_at.desc())
        .limit(1)
    )


def _get_completed_runs(project_id: str, db: Session, *, limit: int = 20) -> list[TestRun]:
    """Get recent completed/failed runs for the run selector."""
    return list(
        db.scalars(
            select(TestRun)
            .where(
                TestRun.project_id == project_id,
                TestRun.run_type == "test",
                TestRun.status.in_([TestRunStatus.passed, TestRunStatus.failed]),
            )
            .order_by(TestRun.created_at.desc())
            .limit(limit)
        )
    )
