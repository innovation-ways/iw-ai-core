"""F-00048: Code Understanding Module + Symbol Views API endpoints.

Extends the existing code.py router created by F-00046 with 4 new endpoints:
  GET  /api/projects/{project_id}/code/modules
  GET  /api/projects/{project_id}/code/modules/{module_slug}
  POST /api/projects/{project_id}/code/modules/{module_slug}/generate
  GET  /api/projects/{project_id}/code/symbol
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.utils.markdown import render_markdown
from orch.db.models import Project, ProjectDoc
from orch.doc_service import DocService
from orch.rag.module_gen import ModuleGenerator
from orch.rag.module_progress import get_or_start_task, get_progress
from orch.rag.parser import parse_modules_from_level1
from orch.rag.symbol_gen import SymbolGenerator

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

    from orch.rag.config import CodeUnderstandingConfig


router = APIRouter(prefix="/api/projects/{project_id}/code", tags=["code"])


def _get_project_or_404(project_id: str, db: Session) -> Project:
    """Fetch a project by ID or raise HTTP 404.

    Args:
        project_id: The project identifier to look up.
        db: Active database session.

    Returns:
        The matching Project ORM row.

    Raises:
        HTTPException: With status 404 if the project does not exist.
    """
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")
    return project


def _get_level1_doc(project_id: str, db: Session) -> ProjectDoc | None:
    """Return the architecture-map doc for a project, or None if not yet generated.

    Args:
        project_id: The project to fetch the doc for.
        db: Active database session.

    Returns:
        The ProjectDoc with slug 'architecture-map', or None.
    """
    return DocService(db).get_doc(project_id, "architecture-map")


def _build_code_config(project: Project) -> CodeUnderstandingConfig:
    """Build the CodeUnderstandingConfig for a project from its DB config and global settings.

    Args:
        project: The Project ORM row whose config block is read.

    Returns:
        Resolved CodeUnderstandingConfig with LLM model, embed model, and index path.
    """
    from orch.config import load_config
    from orch.rag.config import build_code_config_from_project

    cfg = load_config()
    return build_code_config_from_project(project.config, cfg.index_path)


def _module_slug_to_path(module_slug: str, modules: list[dict[str, str]]) -> str | None:
    """Return the filesystem path for a module given its slug, or None if not found.

    Args:
        module_slug: URL-safe slug identifying the module.
        modules: List of module dicts as produced by parse_modules_from_level1.

    Returns:
        The module's relative path string, or None.
    """
    for entry in modules:
        if entry.get("slug") == module_slug:
            return entry.get("path")
    return None


@router.get("/modules", response_class=HTMLResponse)
async def list_modules(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Return a grid of module cards parsed from the architecture-map doc.

    Args:
        project_id: The project whose modules are listed.
        request: The current FastAPI request.
        db: Active database session.

    Returns:
        HTML fragment with module cards, or an empty-state fragment when no index exists.
    """
    _get_project_or_404(project_id, db)
    level1_doc = _get_level1_doc(project_id, db)

    if level1_doc is None:
        templates: Jinja2Templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "fragments/code_empty_state.html",
            {"project_id": project_id},
            status_code=404,
        )

    modules = parse_modules_from_level1(level1_doc.content or "")

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/code_module_cards.html",
        {
            "modules": modules,
            "project_id": project_id,
            "source_doc_slug": level1_doc.slug,
        },
    )


@router.get("/modules/chips", response_class=HTMLResponse)
async def list_modules_chips(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Return a compact horizontal strip of module chips — name + path code.

    Used at the top of the Code page so the user lands on navigation, not on
    the architecture-map prose. Same parser as list_modules; subset rendering.
    """
    _get_project_or_404(project_id, db)
    level1_doc = _get_level1_doc(project_id, db)

    if level1_doc is None:
        templates: Jinja2Templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "fragments/code_empty_state.html",
            {"project_id": project_id},
            status_code=404,
        )

    modules = parse_modules_from_level1(level1_doc.content or "")

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/code_module_chips.html",
        {"modules": modules, "project_id": project_id},
    )


@router.get("/modules/{module_slug}", response_class=HTMLResponse)
async def get_module(
    project_id: str,
    module_slug: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Return the detail panel for a single code module.

    Serves from cache if the module doc already exists, otherwise launches a
    background generation task and polls briefly before returning a generating state.

    Args:
        project_id: The project that owns the module.
        module_slug: URL slug of the module to retrieve.
        request: The current FastAPI request.
        db: Active database session.

    Returns:
        HTML fragment with module documentation or a generating/error state panel.
    """
    project = _get_project_or_404(project_id, db)
    level1_doc = _get_level1_doc(project_id, db)

    if level1_doc is None:
        templates: Jinja2Templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "fragments/code_empty_state.html",
            {"project_id": project_id},
            status_code=404,
        )

    modules = parse_modules_from_level1(level1_doc.content or "")
    module_path = _module_slug_to_path(module_slug, modules)

    if module_path is None:
        raise HTTPException(status_code=404, detail=f"Module {module_slug!r} not found")

    module_entry = next((m for m in modules if m.get("slug") == module_slug), None)
    if module_entry is None:
        raise HTTPException(status_code=404, detail=f"Module {module_slug!r} not found")

    config = _build_code_config(project)
    module_name = module_entry.get("name", module_path)

    gen = ModuleGenerator()
    slug = gen._make_slug(project_id, module_path)  # noqa: SLF001

    # Fast path: doc already generated — return cached content.
    # Use _get_by_slug to query by ProjectDoc.slug field directly,
    # since DocService.get_doc expects doc_id (not slug) and constructs
    # a PK lookup that misses when e2e fixtures seed docs with slug != doc_id.
    cached = gen._get_by_slug(slug, db)  # noqa: SLF001
    if cached is not None:
        doc_html = render_markdown(cached.content) if cached.content else None
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "fragments/code_module_detail.html",
            {
                "project_id": project_id,
                "module": module_entry,
                "doc_html": doc_html,
                "doc_id": cached.id,
                "was_cached": True,
                "generating": False,
                "progress": None,
                "error": None,
            },
        )

    # Slow path: launch (or reuse) a background task with its own DB session.
    async def _launch() -> None:
        await gen.run_standalone(project_id, module_path, module_name, config)

    task = get_or_start_task(project_id, module_path, _launch)

    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(asyncio.shield(task), timeout=0.5)

    # Re-check cache after the short wait — may have just completed.
    fresh = gen._get_by_slug(slug, db)  # noqa: SLF001
    if fresh is not None:
        doc_html = render_markdown(fresh.content) if fresh.content else None
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "fragments/code_module_detail.html",
            {
                "project_id": project_id,
                "module": module_entry,
                "doc_html": doc_html,
                "doc_id": fresh.id,
                "was_cached": False,
                "generating": False,
                "progress": None,
                "error": None,
            },
        )

    progress = get_progress(project_id, module_path)
    error_msg = progress.error if progress and progress.error else None

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/code_module_detail.html",
        {
            "project_id": project_id,
            "module": module_entry,
            "doc_html": None,
            "doc_id": None,
            "was_cached": False,
            "generating": error_msg is None,
            "progress": progress,
            "error": error_msg,
        },
    )


@router.post("/modules/{module_slug}/generate", response_class=HTMLResponse)
async def regenerate_module(
    project_id: str,
    module_slug: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Delete the cached module doc and regenerate it synchronously.

    Args:
        project_id: The project that owns the module.
        module_slug: URL slug of the module to regenerate.
        request: The current FastAPI request.
        db: Active database session.

    Returns:
        HTML fragment with the freshly generated module documentation.
    """
    project = _get_project_or_404(project_id, db)
    level1_doc = _get_level1_doc(project_id, db)

    if level1_doc is None:
        raise HTTPException(status_code=404, detail="Level 1 architecture doc not found")

    modules = parse_modules_from_level1(level1_doc.content or "")
    module_path = _module_slug_to_path(module_slug, modules)

    if module_path is None:
        raise HTTPException(status_code=404, detail=f"Module {module_slug!r} not found")

    module_entry = next((m for m in modules if m.get("slug") == module_slug), None)
    if module_entry is None:
        raise HTTPException(status_code=404, detail=f"Module {module_slug!r} not found")

    module_name = module_entry.get("name", module_path)
    config = _build_code_config(project)

    doc_service = DocService(db)
    module_gen = ModuleGenerator()
    slug = module_gen._make_slug(project_id, module_path)  # noqa: SLF001
    doc_service.delete_doc(project_id, slug)

    doc = await module_gen.generate_level2(project_id, module_path, module_name, config, db)
    doc_html = render_markdown(doc.content) if doc.content else None

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/code_module_detail.html",
        {
            "project_id": project_id,
            "module": module_entry,
            "doc_html": doc_html,
            "doc_id": doc.id,
            "was_cached": False,
            "generating": False,
        },
    )


@router.get("/modules/{module_slug}/diagram", response_class=HTMLResponse)
async def get_module_diagram(
    project_id: str,
    module_slug: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Return the Mermaid diagram panel for a module.

    Args:
        project_id: The project that owns the module.
        module_slug: URL slug of the module whose diagram is fetched.
        request: The current FastAPI request.
        db: Active database session.

    Returns:
        HTML fragment with the diagram DSL for client-side Mermaid rendering.
    """
    _get_project_or_404(project_id, db)

    import re

    doc_service = DocService(db)
    diagram_doc = doc_service.get_doc(project_id, f"diagram-module-{module_slug}")
    diagram_dsl = diagram_doc.content if diagram_doc else None
    diagram_purpose = None
    if diagram_doc and diagram_doc.content:
        m = re.search(r"<!-- purpose: (.*?) -->", diagram_doc.content)
        if m:
            diagram_purpose = m.group(1).strip()

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/code_module_diagram.html",
        {
            "project_id": project_id,
            "slug": module_slug,
            "diagram_dsl": diagram_dsl,
            "diagram_purpose": diagram_purpose,
        },
    )


@router.get("/symbol", response_class=HTMLResponse)
async def explain_symbol(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    file_path: str = Query(..., description="Relative file path within the repo"),
    symbol_name: str | None = Query(None, description="Function or class name"),
) -> Any:
    """Return an LLM-generated explanation for a symbol (function or class) in a file.

    Rejects absolute paths and path traversal attempts.

    Args:
        project_id: The project whose codebase is queried.
        request: The current FastAPI request.
        db: Active database session.
        file_path: Repo-relative path to the source file.
        symbol_name: Optional function or class name within the file.

    Returns:
        HTML fragment with the explanation, or an error message fragment.
    """
    _get_project_or_404(project_id, db)

    if file_path.startswith(("/", "\\")):
        return HTMLResponse(
            '<p class="text-sm text-red-500">Absolute paths not allowed</p>',
            status_code=400,
        )

    normalized = Path(file_path).as_posix()
    if ".." in normalized:
        return HTMLResponse(
            '<p class="text-sm text-red-500">Path traversal not allowed</p>',
            status_code=400,
        )

    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")

    config = _build_code_config(project)
    gen = SymbolGenerator()

    try:
        llm_response = await gen.explain_symbol(project_id, file_path, symbol_name, config, db)
    except FileNotFoundError:
        return HTMLResponse(
            f'<p class="text-sm text-red-500">File not found: {file_path}</p>',
            status_code=404,
        )

    explanation_html = render_markdown(llm_response)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/code_symbol_panel.html",
        {
            "explanation_html": explanation_html,
            "file_path": file_path,
            "symbol_name": symbol_name,
        },
    )
