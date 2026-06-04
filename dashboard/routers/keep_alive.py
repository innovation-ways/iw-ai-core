"""Keep-Alive Scheduler API and page routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from dashboard.dependencies import get_db
from orch import keep_alive_service as svc

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

router = APIRouter(tags=["keep-alive"])

# BIGINT max — PostgreSQL's signed 64-bit integer upper bound.
# slot_id is stored in a BIGINT column; values above this raise
# psycopg.errors.NumericValueOutOfRange at query time (I-00110).
_BIGINT_MAX = 2**63 - 1

ALLOWED_MODELS = ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001"]
ALLOWED_WINDOW_HOURS = [3, 4, 5, 6]


# ---------------------------------------------------------------------------
# Pydantic payloads
# ---------------------------------------------------------------------------


class ConfigPayload(BaseModel):
    model: str
    window_duration_hours: int


class SlotPayload(BaseModel):
    time_hhmm: str


# ---------------------------------------------------------------------------
# Page route
# ---------------------------------------------------------------------------


@router.get("/system/keep-alive", response_class=HTMLResponse)
def keep_alive_page(request: Request, db: Session = Depends(get_db)) -> Response:
    """Full page render for the Keep-Alive Scheduler."""
    config = svc.get_config(db)
    slots = svc.list_slots(db)
    runs = svc.get_recent_runs(db, limit=10)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/system/keep_alive.html",
        {
            "current_project": None,
            "running_count": 0,
            "config": config,
            "slots": slots,
            "runs": runs,
            "available_models": ALLOWED_MODELS,
            "available_durations": ALLOWED_WINDOW_HOURS,
        },
    )


# ---------------------------------------------------------------------------
# Config API
# ---------------------------------------------------------------------------


@router.post("/api/keep-alive/config")
def update_config(
    payload: ConfigPayload, request: Request, db: Session = Depends(get_db)
) -> Response:
    """Update keep-alive config (model + window duration)."""
    if payload.model not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid model {payload.model!r}; must be one of {ALLOWED_MODELS}",
        )
    if payload.window_duration_hours not in ALLOWED_WINDOW_HOURS:
        allowed = ALLOWED_WINDOW_HOURS
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid window_duration_hours {payload.window_duration_hours};"
                f" must be one of {allowed}"
            ),
        )

    svc.upsert_config(db, payload.model, payload.window_duration_hours)
    db.commit()

    config = svc.get_config(db)
    templates: Jinja2Templates = request.app.state.templates
    fragment = templates.TemplateResponse(
        request,
        "fragments/keep_alive_config.html",
        {"config": config},
    )

    return HTMLResponse(
        content=fragment.body.decode("utf-8"),  # type: ignore[union-attr]
        status_code=200,
        headers={"HX-Trigger": '{"showToast": "Config saved"}'},
    )


# ---------------------------------------------------------------------------
# Slots API
# ---------------------------------------------------------------------------


def _render_slots_list(request: Request, db: Session) -> str:
    """Render the slots list fragment and return its HTML string."""
    slots = svc.list_slots(db)
    config = svc.get_config(db)
    templates: Jinja2Templates = request.app.state.templates
    frag = templates.TemplateResponse(
        request,
        "fragments/keep_alive_slots.html",
        {"slots": slots, "config": config},
    )
    return frag.body.decode("utf-8")  # type: ignore[union-attr]


def _render_timeline(request: Request, db: Session) -> str:
    """Render the timeline fragment and return its HTML string."""
    slots = svc.list_slots(db)
    config = svc.get_config(db)
    templates: Jinja2Templates = request.app.state.templates
    frag = templates.TemplateResponse(
        request,
        "fragments/keep_alive_timeline.html",
        {"slots": slots, "config": config},
    )
    return frag.body.decode("utf-8")  # type: ignore[union-attr]


def _slots_and_timeline_response(request: Request, db: Session, primary_html: str) -> HTMLResponse:
    """Combine slots list fragment (primary) + timeline OOB swap into one HTMLResponse."""
    timeline_html = _render_timeline(request, db)
    # OOB swap for the timeline bar
    oob = f'<div id="timeline-bar" hx-swap-oob="innerHTML">{timeline_html}</div>'
    combined = primary_html + "\n" + oob
    return HTMLResponse(content=combined)


@router.get("/api/keep-alive/slots")
def list_slots(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Return slots list fragment (used for htmx refresh after add/delete/toggle)."""
    html = _render_slots_list(request, db)
    return HTMLResponse(content=html)


@router.post("/api/keep-alive/slots")
def add_slot(payload: SlotPayload, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Add a new keep-alive slot."""
    try:
        svc.add_slot(db, payload.time_hhmm)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"A slot for {payload.time_hhmm!r} already exists",
        ) from exc

    slots_html = _render_slots_list(request, db)
    return _slots_and_timeline_response(request, db, slots_html)


@router.delete("/api/keep-alive/slots/{slot_id}")
def delete_slot(
    slot_id: Annotated[int, Path(ge=1, le=_BIGINT_MAX)],
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Delete a keep-alive slot."""
    deleted = svc.delete_slot(db, slot_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Slot not found")
    db.commit()

    slots_html = _render_slots_list(request, db)
    return _slots_and_timeline_response(request, db, slots_html)


@router.patch("/api/keep-alive/slots/{slot_id}/toggle")
def toggle_slot(
    slot_id: Annotated[int, Path(ge=1, le=_BIGINT_MAX)],
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Toggle slot enabled/disabled."""
    slot = svc.toggle_slot(db, slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found")
    db.commit()

    templates: Jinja2Templates = request.app.state.templates
    row_frag = templates.TemplateResponse(
        request,
        "fragments/keep_alive_slot_row.html",
        {"slot": slot},
    )
    row_html = row_frag.body.decode("utf-8")  # type: ignore[union-attr]

    return _slots_and_timeline_response(request, db, row_html)


# ---------------------------------------------------------------------------
# Runs API
# ---------------------------------------------------------------------------


@router.get("/api/keep-alive/runs", response_class=HTMLResponse)
def list_runs(request: Request, db: Session = Depends(get_db)) -> Response:
    """Return the last-10-runs table fragment."""
    runs = svc.get_recent_runs(db, limit=10)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/keep_alive_runs.html",
        {"runs": runs},
    )


# ---------------------------------------------------------------------
# Allow pydantic models to be imported from this module
# ---------------------------------------------------------------------
__all__ = ["ConfigPayload", "SlotPayload"]
