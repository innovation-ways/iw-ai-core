"""FastAPI dashboard application factory for IW AI Core."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.requests import Request  # noqa: TC002
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dashboard.middlewares.alembic_guard import AlembicGuardMiddleware, is_db_stale
from dashboard.routers import (
    actions,
    batches,
    code,
    code_qa,
    code_ui,
    containers,
    coverage,
    daemon_control,
    docs,
    docs_global,
    healthz,
    items,
    jobs_ui,
    keep_alive,
    oss,
    project_dashboard,
    project_pages,
    projects,
    quality,
    research,
    running,
    search,
    sse,
    staleness,
    system,
    tests,
    usage,
    worktrees,
)
from dashboard.utils.timing import TimingMiddleware
from orch.db.alembic_guard import check_db_at_head
from orch.db.identity import verify_instance_identity
from orch.db.session import SessionLocal, engine
from orch.test_runner import mark_orphaned_runs

_HERE = Path(__file__).resolve().parent
_STATIC_DIR = _HERE / "static"
_TEMPLATES_DIR = _HERE / "templates"

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
    count = mark_orphaned_runs()
    if count:
        logger.warning("Marked %d orphaned test run(s) as error on startup", count)

    session = SessionLocal()
    try:
        identity_status = verify_instance_identity(session)
        if identity_status.mode == "match":
            logger.info("Dashboard: DB identity verified (%s)", str(identity_status.actual)[:8])
        elif identity_status.mode == "bootstrap":
            logger.info(
                "Dashboard: %s",
                identity_status.message,
            )
    except Exception as exc:
        logger.error("Dashboard: %s", exc)
        raise
    finally:
        session.close()

    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="IW AI Core Dashboard",
        description="Real-time management interface for IW AI Core orchestration platform.",
        version="0.1.0",
        lifespan=_lifespan,
        docs_url="/api-docs",
        redoc_url="/api-redoc",
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # Register timing middleware
    app.add_middleware(
        TimingMiddleware,
        engine=engine,
        slow_request_ms=int(os.environ.get("IW_CORE_SLOW_REQUEST_MS", "500")),
    )

    # Register alembic guard middleware (R3 — throttle re-checks at most once per 10s)
    app.add_middleware(AlembicGuardMiddleware)

    # Initial alembic guard check at app construction (R3).
    # Suppress failures: if the DB is unreachable at boot, the middleware
    # will retry on each request (with the same suppress) and the banner
    # stays hidden. Mirrors the middleware's contextlib.suppress pattern.
    try:
        app.state.alembic_guard_status = check_db_at_head()
    except Exception:  # noqa: BLE001
        logger.exception("alembic guard check failed at startup; continuing")
        app.state.alembic_guard_status = None

    # Configure Jinja2 templates and store on app state so routers can access it
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    def _fmt_ts_time(ts: float) -> str:
        import datetime as _dt_module

        return (
            _dt_module.datetime.fromtimestamp(ts, tz=_dt_module.UTC)
            .astimezone()
            .strftime("%H:%M:%S")
        )

    def _localdt(dt: object, fmt: str = "%b %d %H:%M") -> str:
        import datetime as _dt_module

        if not isinstance(dt, _dt_module.datetime):
            return ""
        return dt.astimezone().strftime(fmt)

    def _timeago(dt: object) -> str:
        import datetime as _dt_module

        if not isinstance(dt, _dt_module.datetime):
            return ""
        now = _dt_module.datetime.now(tz=_dt_module.UTC)
        diff = now - dt.astimezone(tz=_dt_module.UTC)
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        minutes = int(seconds / 60)
        if minutes < 60:
            return f"{minutes}m ago"
        hours = int(minutes / 60)
        if hours < 24:
            return f"{hours}h ago"
        days = int(hours / 24)
        if days < 30:
            return f"{days}d ago"
        months = int(days / 30)
        if months < 12:
            return f"{months}mo ago"
        years = int(months / 12)
        return f"{years}y ago"

    templates.env.filters["intcomma"] = lambda n: f"{n:,}" if isinstance(n, int) else str(n)
    templates.env.filters["timeago"] = _timeago
    templates.env.filters["fmt_ts_time"] = _fmt_ts_time
    templates.env.filters["localdt"] = _localdt

    def _is_db_stale(request: Request) -> bool:
        return is_db_stale(request)

    templates.env.globals["is_db_stale"] = _is_db_stale
    app.state.templates = templates

    # Health check endpoint (used by browser_verification steps and monitoring)
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "iw-ai-core-dashboard"}

    # Register routers
    app.include_router(healthz.router)
    app.include_router(projects.router)
    app.include_router(running.router)
    app.include_router(actions.router)
    app.include_router(sse.router)
    app.include_router(system.router)
    app.include_router(keep_alive.router)
    app.include_router(daemon_control.router)
    app.include_router(project_dashboard.router)
    app.include_router(batches.router)
    app.include_router(items.router)
    app.include_router(tests.router)
    app.include_router(quality.router)
    app.include_router(oss.router)
    app.include_router(project_pages.router)
    app.include_router(jobs_ui.router)
    app.include_router(search.router)
    app.include_router(worktrees.router)
    app.include_router(containers.router)
    app.include_router(docs.router)
    app.include_router(docs_global.router)
    app.include_router(code.router)
    app.include_router(code_ui.router)
    app.include_router(code_qa.router)
    app.include_router(research.router)
    app.include_router(staleness.router)
    app.include_router(coverage.router)
    app.include_router(usage.router)

    return app
