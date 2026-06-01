"""Runtime override endpoints for per-item and per-step (CLI, model) overrides.

GET  /project/{project_id}/api/runtime-options
     — returns enabled rows from agent_runtime_options ordered by sort_order, id.

PATCH /project/{project_id}/api/item/{item_id}/runtime-override
     — set/clear item-level override via form field option_id (integer or empty).

PATCH /project/{project_id}/api/item/{item_id}/step/{step_id}/runtime-override
     — set/clear step-level override via form field option_id (integer or empty).

PATCH /project/{project_id}/api/item/{item_id}/runtime-override/bulk
     — apply override to all editable steps (pending | failed | paused) in one transaction.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.routers import items as items_router
from orch.agent_runtime.audit import emit_runtime_override_changed
from orch.db.models import (
    AgentRuntimeOption,
    StepStatus,
    WorkflowStep,
    WorkItem,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


router = APIRouter(prefix="/project/{project_id}/api")

# Editable step statuses for override purposes.
# NOTE: StepStatus has no "paused" value — "paused" is a WorkItemStatus, not a
# StepStatus. Steps keep their individual status while the item is paused.
_EDITABLE_STEP_STATUSES = {StepStatus.pending, StepStatus.failed}

# Actor when no real auth is available
_ACTOR = "dashboard"


# ---------------------------------------------------------------------------
# GET /runtime-options — catalogue dropdown source
# ---------------------------------------------------------------------------


@router.get("/runtime-options")
def get_runtime_options(
    project_id: str,  # noqa: ARG001 — declared by router prefix, not used (returns all enabled rows)
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Return enabled agent_runtime_options rows ordered by sort_order, id.

    This endpoint powers the frontend's dropdown population.
    """
    rows = list(
        db.scalars(
            select(AgentRuntimeOption)
            .where(AgentRuntimeOption.enabled.is_(True))
            .order_by(AgentRuntimeOption.sort_order, AgentRuntimeOption.id)
        ).all()
    )
    data = [
        {
            "id": r.id,
            "cli_tool": r.cli_tool,
            "model": r.model,
            "cli_label": r.cli_label,
            "model_label": r.model_label,
            "display_name": r.display_name,
            "is_default": r.is_default,
        }
        for r in rows
    ]
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "max-age=60"},
    )


# ---------------------------------------------------------------------------
# PATCH /item/{item_id}/runtime-override — item-level override
# ---------------------------------------------------------------------------


def _get_item_or_404(db: Session, project_id: str, item_id: str) -> WorkItem:
    item = db.scalar(
        select(WorkItem).where(
            WorkItem.project_id == project_id,
            WorkItem.id == item_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail=f"Work item {item_id} not found")
    return item


def _get_step_or_404(db: Session, project_id: str, item_id: str, step_id: str) -> WorkflowStep:
    step = db.scalar(
        select(WorkflowStep).where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.step_id == step_id,
        )
    )
    if step is None:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found for item {item_id}")
    return step


def _validate_option_id(db: Session, option_id: int | None) -> int | None:
    """Return option_id if it references an enabled row; raise 404 otherwise."""
    if option_id is None:
        return None
    row = db.scalar(
        select(AgentRuntimeOption).where(
            AgentRuntimeOption.id == option_id,
            AgentRuntimeOption.enabled.is_(True),
        )
    )
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Runtime option {option_id} not found or disabled"
        )
    return option_id


def _item_has_editable_steps(db: Session, item: WorkItem) -> bool:
    """Return True if the item has at least one step in an editable status."""
    count = db.scalar(
        select(WorkflowStep.id)
        .where(
            WorkflowStep.project_id == item.project_id,
            WorkflowStep.work_item_id == item.id,
            WorkflowStep.status.in_(_EDITABLE_STEP_STATUSES),
        )
        .limit(1)
    )
    return count is not None


def _render_steps_fragment(request: Request, db: Session, project_id: str, item_id: str) -> str:
    """Render the swappable steps-table fragment for runtime-override PATCH responses."""
    project = items_router._get_project_or_404(project_id, db)  # noqa: SLF001
    item = _get_item_or_404(db, project_id, item_id)
    steps = items_router._get_steps(project_id, item_id, db, project)  # noqa: SLF001
    step_run_counts: dict[str, int] = {s.step_id: s.run_count for s in steps if not s.is_synthetic}

    runtime_options = list(
        db.scalars(
            select(AgentRuntimeOption)
            .where(AgentRuntimeOption.enabled.is_(True))
            .order_by(AgentRuntimeOption.sort_order, AgentRuntimeOption.id)
        ).all()
    )
    runtime_options_list = [
        {
            "id": r.id,
            "cli_tool": r.cli_tool,
            "model": r.model,
            "cli_label": r.cli_label,
            "model_label": r.model_label,
            "display_name": r.display_name,
            "is_default": r.is_default,
        }
        for r in runtime_options
    ]

    # CR-00070 S01: compute the label shown in the per-step dropdown empty option
    inherited_runtime_label = items_router._get_inherited_runtime_label(db, project_id, item)  # noqa: SLF001

    templates = request.app.state.templates
    response = templates.TemplateResponse(
        request,
        "fragments/item_steps_table.html",
        {
            "item": item,
            "steps": steps,
            "step_run_counts": step_run_counts,
            "runtime_options": runtime_options_list,
            "runtime_option_labels": items_router._all_runtime_option_labels(db),  # noqa: SLF001
            "inherited_runtime_label": inherited_runtime_label,
        },
    )
    return bytes(response.body).decode("utf-8")


@router.patch("/item/{item_id}/runtime-override", response_class=Response)
def patch_item_runtime_override(
    project_id: str,
    item_id: str,
    option_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> Response:
    """Set or clear the item-level runtime override.

    Validation:
    - Item must exist and belong to project_id (404 otherwise).
    - Item must have at least one editable step (pending|failed|paused), else 400.
    - option_id, if given, must reference an enabled row (404 otherwise).
    """
    item = _get_item_or_404(db, project_id, item_id)

    if not _item_has_editable_steps(db, item):
        raise HTTPException(
            status_code=400,
            detail="Item has no editable steps; cannot apply override.",
        )

    old_option_id = item.agent_runtime_option_id
    new_option_id = _validate_option_id(db, option_id)

    item.agent_runtime_option_id = new_option_id

    emit_runtime_override_changed(
        db,
        project_id=project_id,
        item_id=item_id,
        scope="item",
        step_ids=None,
        old_option_id=old_option_id,
        new_option_id=new_option_id,
        actor=_ACTOR,
    )

    return Response(status_code=204)


# ---------------------------------------------------------------------------
# PATCH /item/{item_id}/step/{step_id}/runtime-override — step-level override
# ---------------------------------------------------------------------------


@router.patch("/item/{item_id}/step/{step_id}/runtime-override", response_class=HTMLResponse)
def patch_step_runtime_override(
    project_id: str,
    item_id: str,
    step_id: str,
    request: Request,
    option_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> Response:
    """Set or clear the step-level runtime override.

    Validation:
    - Item + step must exist with the given (project_id, item_id, step_id) triple (404).
    - Step status must be in {pending, failed, paused}, else 409 Conflict.
    - option_id, if given, must reference an enabled row (404 otherwise).
    """
    # Validate item
    _get_item_or_404(db, project_id, item_id)

    step = _get_step_or_404(db, project_id, item_id, step_id)

    if step.status not in _EDITABLE_STEP_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Step is not editable (status={step.status.value}).",
        )

    old_option_id = step.agent_runtime_option_id
    new_option_id = _validate_option_id(db, option_id)

    step.agent_runtime_option_id = new_option_id

    emit_runtime_override_changed(
        db,
        project_id=project_id,
        item_id=item_id,
        scope="step",
        step_ids=[step_id],
        old_option_id=old_option_id,
        new_option_id=new_option_id,
        actor=_ACTOR,
    )

    fragment_html = _render_steps_fragment(request, db, project_id, item_id)
    # Contract: return the steps fragment; HX-Trigger.showToast provides user feedback.
    return HTMLResponse(
        content=fragment_html,
        status_code=200,
        headers={
            "HX-Trigger": json.dumps({"showToast": {"message": "Model updated", "type": "success"}})
        },
    )


# ---------------------------------------------------------------------------
# PATCH /item/{item_id}/runtime-override/bulk — bulk step override
# ---------------------------------------------------------------------------


@router.patch("/item/{item_id}/runtime-override/bulk", response_class=HTMLResponse)
def patch_bulk_runtime_override(
    project_id: str,
    item_id: str,
    request: Request,
    option_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
) -> Response:
    """Apply an override to every editable step under the item in one transaction.

    Steps with non-editable status are silently skipped (no error).
    If no steps are updated, no DaemonEvent is emitted (boundary case).

    Validation:
    - Item must exist and belong to project_id (404 otherwise).
    - option_id, if given, must reference an enabled row (404 otherwise).
    """
    _get_item_or_404(db, project_id, item_id)

    new_option_id = _validate_option_id(db, option_id)

    # Collect all editable steps in a single query
    editable_steps = list(
        db.scalars(
            select(WorkflowStep).where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
                WorkflowStep.status.in_(_EDITABLE_STEP_STATUSES),
            )
        ).all()
    )
    changed_steps = [
        step for step in editable_steps if step.agent_runtime_option_id != new_option_id
    ]
    updated_count = len(changed_steps)

    if updated_count >= 1:
        old_option_id = changed_steps[0].agent_runtime_option_id
        for step in changed_steps:
            step.agent_runtime_option_id = new_option_id

        emit_runtime_override_changed(
            db,
            project_id=project_id,
            item_id=item_id,
            scope="bulk",
            step_ids=[s.step_id for s in changed_steps],
            old_option_id=old_option_id,
            new_option_id=new_option_id,
            actor=_ACTOR,
        )
        toast_message = f"Model updated for {updated_count} step(s)"
        toast_type = "success"
    else:
        # zero editable steps → no event, no changes
        toast_message = "No editable steps to update"
        toast_type = "info"

    fragment_html = _render_steps_fragment(request, db, project_id, item_id)
    # Contract: return the steps fragment; HX-Trigger.showToast provides user feedback.
    return HTMLResponse(
        content=fragment_html,
        status_code=200,
        headers={
            "HX-Trigger": json.dumps({"showToast": {"message": toast_message, "type": toast_type}})
        },
    )
