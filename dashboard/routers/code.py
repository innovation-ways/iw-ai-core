"""F-00048: Code Understanding Module + Symbol Views API endpoints.

Extends the existing code.py router created by F-00046 with 4 new endpoints:
  GET  /api/projects/{project_id}/code/modules
  GET  /api/projects/{project_id}/code/modules/{module_slug}
  POST /api/projects/{project_id}/code/modules/{module_slug}/generate
  GET  /api/projects/{project_id}/code/symbol
"""

from __future__ import annotations

import asyncio
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
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")
    return project


def _get_level1_doc(project_id: str, db: Session) -> ProjectDoc | None:
    return DocService(db).get_doc(project_id, "architecture-map")


def _build_code_config(project: Project) -> CodeUnderstandingConfig:
    from orch.rag.config import CodeUnderstandingConfig

    code_cfg_dict = (project.config or {}).get("code_understanding", {})
    return CodeUnderstandingConfig(**code_cfg_dict)


def _module_slug_to_path(module_slug: str, modules: list[dict[str, str]]) -> str | None:
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


@router.get("/modules/{module_slug}", response_class=HTMLResponse)
async def get_module(
    project_id: str,
    module_slug: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
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
    cached = DocService(db).get_doc(project_id, slug)
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

    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=0.5)
    except TimeoutError:
        pass

    # Re-check cache after the short wait — may have just completed.
    fresh = DocService(db).get_doc(project_id, slug)
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
            "was_cached": False,
            "generating": False,
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
