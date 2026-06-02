"""Container health page — read-only view of all per-worktree Docker stacks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from dashboard.dependencies import get_db
from orch.daemon.container_info import ContainerStack, remove_stack, scan_stacks

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/system")

_AGE_BUCKETS: dict[str, tuple[str, Any]] = {
    "lt1h": ("< 1h", lambda s: s.age_secs < 3600),
    "1to6h": ("1–6h", lambda s: 3600 <= s.age_secs < 21600),
    "6to24h": ("6–24h", lambda s: 21600 <= s.age_secs < 86400),
    "gt24h": ("> 24h", lambda s: s.age_secs >= 86400),
}

_REMOVABLE = {"stale", "orphan", "malformed"}


def _apply_filters(
    stacks: list[ContainerStack],
    project: list[str] | None,
    classification: list[str] | None,
    item: str | None,
    age: str | None,
) -> list[ContainerStack]:
    """Filter a list of container stacks by the provided criteria.

    Args:
        stacks: Full list of detected container stacks.
        project: Optional list of project IDs to include.
        classification: Optional list of classification labels to include.
        item: Optional substring to match against item_id (case-insensitive).
        age: Optional age bucket key from _AGE_BUCKETS.

    Returns:
        Filtered list of ContainerStack entries.
    """
    result = stacks
    if project:
        result = [s for s in result if s.project_id in project]
    if classification:
        result = [s for s in result if s.classification in classification]
    if item:
        needle = item.lower()
        result = [s for s in result if needle in (s.item_id or "").lower()]
    if age and age in _AGE_BUCKETS:
        pred = _AGE_BUCKETS[age][1]
        result = [s for s in result if pred(s)]
    return result


@router.get("/containers", response_class=HTMLResponse)
def containers_page(
    request: Request,
    db: Session = Depends(get_db),
    project: list[str] = Query(default=None),
    classification: list[str] = Query(default=None),
    item: str | None = Query(default=None),
    age: str | None = Query(default=None),
) -> Any:
    """Render the full containers health page with optional filter controls.

    Args:
        request: The current FastAPI request.
        db: Active database session.
        project: Project ID filter(s).
        classification: Classification label filter(s) (active/stale/orphan/malformed).
        item: Partial item ID filter.
        age: Age bucket filter key.

    Returns:
        Full HTML page with the filtered container stack table.
    """
    templates: Jinja2Templates = request.app.state.templates
    all_stacks = scan_stacks(db)
    stacks = _apply_filters(all_stacks, project, classification, item, age)

    all_projects = sorted({s.project_id for s in all_stacks if s.project_id})

    return templates.TemplateResponse(
        request,
        "pages/system/containers.html",
        {
            "current_project": None,
            "stacks": stacks,
            "total": len(all_stacks),
            "filtered": len(stacks),
            "all_projects": all_projects,
            "all_classifications": ["active", "stale", "orphan", "malformed"],
            "project_filter": project or [],
            "classification_filter": classification or [],
            "item_filter": item or "",
            "age_filter": age or "",
            "age_buckets": {k: v[0] for k, v in _AGE_BUCKETS.items()},
        },
    )


@router.get("/containers/table", response_class=HTMLResponse)
def containers_table(
    request: Request,
    db: Session = Depends(get_db),
    project: list[str] = Query(default=None),
    classification: list[str] = Query(default=None),
    item: str | None = Query(default=None),
    age: str | None = Query(default=None),
) -> Any:
    """htmx fragment — auto-refresh every 30 s."""
    templates: Jinja2Templates = request.app.state.templates
    all_stacks = scan_stacks(db)
    stacks = _apply_filters(all_stacks, project, classification, item, age)

    return templates.TemplateResponse(
        request,
        "fragments/containers_table.html",
        {
            "stacks": stacks,
            "total": len(all_stacks),
            "filtered": len(stacks),
            "project_filter": project or [],
            "classification_filter": classification or [],
            "item_filter": item or "",
            "age_filter": age or "",
        },
    )


@router.post("/containers/{compose_project}/remove", response_class=HTMLResponse)
def containers_remove(
    compose_project: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Tear down a stale or orphan compose stack and return the refreshed table."""
    templates: Jinja2Templates = request.app.state.templates

    # Validate the stack is removable before acting
    all_stacks = scan_stacks(db)
    target = next((s for s in all_stacks if s.compose_project == compose_project), None)
    if target is not None and target.classification not in _REMOVABLE:
        # Return unchanged table — active stacks must not be removed from the UI
        return templates.TemplateResponse(
            request,
            "fragments/containers_table.html",
            {"stacks": all_stacks, "total": len(all_stacks), "filtered": len(all_stacks)},
        )

    remove_stack(compose_project)

    # Re-scan after removal
    stacks = scan_stacks(db)
    return templates.TemplateResponse(
        request,
        "fragments/containers_table.html",
        {"stacks": stacks, "total": len(stacks), "filtered": len(stacks)},
    )
