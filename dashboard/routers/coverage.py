"""Coverage dashboard router — /system/coverage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from dashboard.services.coverage_service import load_coverage

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/system/coverage", tags=["system"])


@router.get("", response_class=HTMLResponse)
def coverage_page(request: Request) -> HTMLResponse:
    """Render the system-level test coverage page.

    Args:
        request: The current FastAPI request.

    Returns:
        Full HTML page with per-package coverage summaries.
    """
    view = load_coverage()
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="pages/system/coverage.html",
        context={"view": view},
    )


@router.get("/files/{package}", response_class=HTMLResponse)
def coverage_files_fragment(request: Request, package: str) -> HTMLResponse:
    """Return the file-level coverage fragment for a specific package.

    Args:
        request: The current FastAPI request.
        package: Python package name whose file details are returned.

    Returns:
        HTML fragment with per-file coverage rows, or 404 if the package is unknown.
    """
    view = load_coverage()
    templates: Jinja2Templates = request.app.state.templates
    if package not in view.files_by_package:
        return HTMLResponse(status_code=404)
    return templates.TemplateResponse(
        request=request,
        name="fragments/coverage_files.html",
        context={"package": package, "files": view.files_by_package[package]},
    )
