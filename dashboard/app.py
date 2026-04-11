"""FastAPI dashboard application factory for IW AI Core."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dashboard.routers import (
    actions,
    batches,
    daemon_control,
    items,
    project_dashboard,
    project_pages,
    projects,
    running,
    search,
    sse,
    system,
    tests,
)

_HERE = Path(__file__).resolve().parent
_STATIC_DIR = _HERE / "static"
_TEMPLATES_DIR = _HERE / "templates"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="IW AI Core Dashboard",
        description="Real-time management interface for IW AI Core orchestration platform.",
        version="0.1.0",
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # Configure Jinja2 templates and store on app state so routers can access it
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    def _fmt_ts_time(ts: float) -> str:
        import datetime as _dt_module

        return _dt_module.datetime.fromtimestamp(ts).strftime("%H:%M:%S")

    templates.env.filters["fmt_ts_time"] = _fmt_ts_time
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
    app.include_router(project_pages.router)
    app.include_router(search.router)

    return app
