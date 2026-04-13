"""FastAPI dashboard application factory for IW AI Core."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

from fastapi import FastAPI

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dashboard.routers import (
    actions,
    batches,
    daemon_control,
    docs,
    docs_global,
    items,
    project_dashboard,
    project_pages,
    projects,
    quality,
    running,
    search,
    sse,
    system,
    tests,
    worktrees,
)
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
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="IW AI Core Dashboard",
        description="Real-time management interface for IW AI Core orchestration platform.",
        version="0.1.0",
        lifespan=_lifespan,
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

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

    templates.env.filters["fmt_ts_time"] = _fmt_ts_time
    templates.env.filters["localdt"] = _localdt
    templates.env.filters["urlencode"] = quote
    app.state.templates = templates

    # Register routers
    app.include_router(projects.router)
    app.include_router(running.router)
    app.include_router(actions.router)
    app.include_router(sse.router)
    app.include_router(system.router)
    app.include_router(daemon_control.router)
    app.include_router(project_dashboard.router)
    app.include_router(batches.router)
    app.include_router(items.router)
    app.include_router(tests.router)
    app.include_router(quality.router)
    app.include_router(project_pages.router)
    app.include_router(search.router)
    app.include_router(worktrees.router)
    app.include_router(docs.router)
    app.include_router(docs_global.router)

    return app
