"""Help fragment router — delivers contextual help popover content by slug.

Read-only. Returns a Jinja help fragment by slug. See F-00080.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

if __name__ == "__main__":
    import uvicorn

    from dashboard.app import create_app

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=9900)  # noqa: S104


#: Slug validation regex: lowercase alphanumeric, underscores, hyphens; 0-31 chars.
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")

#: Absolute path to the help fragments directory within the dashboard package.
_HELP_FRAGMENTS_DIR = Path(__file__).resolve().parent.parent / "templates" / "_partials" / "help"

#: Mapping from help slug to the docs URL for the "Open full docs" link (CR-00042).
_SLUG_TO_DOC: dict[str, str] = {
    "all_active": "/system/docs/IW_AI_Core_Daemon_Design",
    "batch_detail": "/system/docs/IW_AI_Core_Daemon_Design",
    "batches": "/system/docs/IW_AI_Core_Daemon_Design",
    "code": "/system/docs/IW_AI_Core_Architecture",
    "config": "/system/docs/IW_AI_Core_Tech_Stack",
    "containers": "/system/docs/IW_AI_Core_Worktree_Isolation",
    "coverage": "/system/docs/IW_AI_Core_Tech_Stack",
    "docs": "/system/docs/IW_AI_Core_Dashboard_Design",
    "history": "/system/docs/IW_AI_Core_CLI_Spec",
    "item_detail": "/system/docs/IW_AI_Core_Architecture",
    "job_detail": "/system/docs/IW_AI_Core_Daemon_Design",
    "jobs": "/system/docs/IW_AI_Core_Daemon_Design",
    "keep_alive": "/system/docs/IW_AI_Core_Daemon_Design",
    "projects": "/system/docs/IW_AI_Core_Architecture",
    "quality": "/system/docs/IW_AI_Core_Tech_Stack",
    "queue": "/system/docs/IW_AI_Core_CLI_Spec#iw-approve",
    "research": "/system/docs/IW_AI_Core_Architecture",
    "running": "/system/docs/IW_AI_Core_Daemon_Design",
    "search": "/system/docs/IW_AI_Core_Architecture",
    "status": "/system/docs/IW_AI_Core_DB_Setup",
    "tests": "/system/docs/IW_AI_Core_Tech_Stack",
    "worktrees": "/system/docs/IW_AI_Core_Daemon_Design",
}

#: Module-level cached allow-list of valid slugs.
_ALLOWED_SLUGS: set[str] = set()

#: Flag so the warning is logged only once.
_LOGGED_EMPTY_WARN = False

logger = logging.getLogger(__name__)


def _load_allow_list() -> set[str]:
    """Scan the help fragments directory and return the set of valid slugs.

    Returns an empty set if the directory does not exist or contains no files.
    Logs a WARNING once if the directory is absent.
    """
    global _LOGGED_EMPTY_WARN  # noqa: PLW0603

    if not _HELP_FRAGMENTS_DIR.is_dir():
        if not _LOGGED_EMPTY_WARN:
            logger.warning(
                "Help fragments directory not found; /_help endpoint will return 404 for all slugs."
            )
            _LOGGED_EMPTY_WARN = True
        return set()

    slugs = {p.stem for p in _HELP_FRAGMENTS_DIR.glob("*.html") if p.is_file() and p.stem}
    if not slugs and not _LOGGED_EMPTY_WARN:
        logger.warning(
            "Help fragments directory not found; /_help endpoint will return 404 for all slugs."
        )
        _LOGGED_EMPTY_WARN = True
    return slugs


# Compute the allow-list once at module load time.
_ALLOWED_SLUGS = _load_allow_list()


def _render_help_fragment(slug: str, templates: Jinja2Templates, docs_link: str) -> str:
    """Render and return the HTML string for the named help fragment."""
    template_name = f"_partials/help/{slug}.html"
    fragment = templates.get_template(template_name)
    return fragment.render(docs_link=docs_link)


if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates


router = APIRouter(tags=["help"])


@router.get("/_help/{slug}", response_class=HTMLResponse)
def get_help_fragment(slug: str, request: Request) -> HTMLResponse:
    """Read-only. Returns a Jinja help fragment by slug. See F-00080."""
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=404, detail="No help available for this page")

    if slug not in _ALLOWED_SLUGS:
        raise HTTPException(status_code=404, detail="No help available for this page")

    templates: Jinja2Templates = request.app.state.templates
    docs_link = _SLUG_TO_DOC.get(slug, "/system/docs/IW_AI_Core_Architecture")
    html_content = _render_help_fragment(slug, templates, docs_link)
    return HTMLResponse(content=html_content)
