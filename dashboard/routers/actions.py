"""Dashboard action endpoints — kill, restart, skip, restart-from, confirm dialog."""

from __future__ import annotations

import contextlib
import json
import os
import signal
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select

from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    RunStatus,
    StepRun,
    StepStatus,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
)

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session


router = APIRouter(prefix="/project/{project_id}/api")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ACTION_LABELS: dict[str, tuple[str, str, str]] = {
    # action-slug → (dialog title, dialog description template, confirm button label)
    "kill-step": (
        "Kill step?",
        "This will send SIGTERM to the running process.",
        "Kill",
    ),
    "restart-step": (
        "Restart step?",
        "Creates a new run. The daemon will launch it on the next poll.",
        "Restart",
    ),
    "skip-step": (
        "Skip step?",
        "Marks the step as skipped. The daemon will advance to the next step.",
        "Skip",
    ),
}

# Item-level action labels — keyed by action slug
_ITEM_ACTION_LABELS: dict[str, tuple[str, str, str, bool]] = {
    # action-slug → (dialog title, description, confirm label, danger?)
    "approve": (
        "Approve item?",
        "This marks the item as approved for execution.",
        "Approve",
        False,
    ),
    "unapprove": (
        "Unapprove item?",
        "This reverts the item to draft status.",
        "Unapprove",
        True,
    ),
    "restart": (
        "Restart item?",
        "Resets all failed/completed steps to pending and queues for re-execution.",
        "Restart",
        False,
    ),
    "pause": (
        "Pause item?",
        "Pauses the item. Running steps will finish but no new steps will start.",
        "Pause",
        True,
    ),
    "resume": (
        "Resume item?",
        "Resumes execution from where it left off.",
        "Resume",
        False,
    ),
}


def _get_step(db: Session, project_id: str, item_id: str, step_id: str) -> WorkflowStep:
    """Look up a WorkflowStep by (project_id, item_id, step_id string)."""
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


def _get_last_run(db: Session, step_db_id: int) -> StepRun | None:
    """Return the most recent StepRun for a workflow step."""
    return db.scalar(
        select(StepRun)
        .where(StepRun.step_id == step_db_id)
        .order_by(StepRun.run_number.desc())
        .limit(1)
    )


def _get_item(db: Session, project_id: str, item_id: str) -> WorkItem:
    item = db.scalar(
        select(WorkItem).where(
            WorkItem.project_id == project_id,
            WorkItem.id == item_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail=f"Work item {item_id} not found")
    return item


def _emit(
    db: Session,
    event_type: str,
    project_id: str,
    entity_id: str,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        DaemonEvent(
            project_id=project_id,
            event_type=event_type,
            entity_id=entity_id,
            message=message,
            event_metadata=metadata or {},
        )
    )


def _action_response(
    message: str,
    toast_type: str = "success",
    *,
    reload: bool = False,
) -> Response:
    """Return 204 with HX-Trigger header to show a toast."""
    toast: dict[str, Any] = {"message": message, "type": toast_type}
    if reload:
        toast["reload"] = True
    trigger = json.dumps({"showToast": toast})
    return Response(
        status_code=204,
        headers={
            "HX-Trigger": trigger,
            "HX-Refresh": "false",
        },
    )


# ---------------------------------------------------------------------------
# Confirm dialog (GET — returns HTML fragment)
# ---------------------------------------------------------------------------


@router.get(
    "/confirm/{action}/{item_id}/{step_id}",
    response_class=HTMLResponse,
)
def confirm_dialog(
    project_id: str,
    action: str,
    item_id: str,
    step_id: str,
    request: Request,
) -> Any:
    templates: Jinja2Templates = request.app.state.templates

    label_info = _ACTION_LABELS.get(action)
    if label_info is None:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    title, description, confirm_label = label_info

    # Build the URL that the confirm button will POST to
    action_url = f"/project/{project_id}/api/item/{item_id}/{action}/{step_id}"

    return templates.TemplateResponse(
        request,
        "fragments/confirm_action.html",
        {
            "title": f"{title.rstrip('?')} {step_id}?",
            "description": description,
            "confirm_url": action_url,
            "confirm_label": confirm_label,
            "danger": action == "kill-step",
        },
    )


# ---------------------------------------------------------------------------
# Kill step
# ---------------------------------------------------------------------------


@router.post(
    "/item/{item_id}/kill-step/{step_id}",
    response_class=Response,
)
def kill_step(
    project_id: str,
    item_id: str,
    step_id: str,
    db: Session = Depends(get_db),
) -> Any:
    step = _get_step(db, project_id, item_id, step_id)

    run = db.scalar(
        select(StepRun).where(
            StepRun.step_id == step.id,
            StepRun.status == RunStatus.running,
        )
    )
    if run is None:
        raise HTTPException(
            status_code=422,
            detail=f"Step {step_id} is not running (no active run found)",
        )

    # Send SIGTERM immediately
    if run.pid is not None:
        with contextlib.suppress(ProcessLookupError):
            os.kill(run.pid, signal.SIGTERM)

    now = datetime.now(UTC)
    run.status = RunStatus.killed
    run.completed_at = now
    if run.started_at is not None:
        run.duration_secs = (now - run.started_at).total_seconds()
    run.error_message = "Killed by user"

    step.status = StepStatus.failed
    step.completed_at = now

    _emit(db, "step_killed", project_id, item_id, f"Step {step_id} killed by user")
    db.commit()

    return _action_response(f"Step {step_id} killed.", toast_type="warning")


# ---------------------------------------------------------------------------
# Restart step
# ---------------------------------------------------------------------------


@router.post(
    "/item/{item_id}/restart-step/{step_id}",
    response_class=Response,
)
def restart_step(
    project_id: str,
    item_id: str,
    step_id: str,
    db: Session = Depends(get_db),
) -> Any:
    step = _get_step(db, project_id, item_id, step_id)

    if step.status not in (StepStatus.failed, StepStatus.skipped):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot restart: step status is '{step.status.value}' (must be failed or skipped)"
            ),
        )

    last_run = _get_last_run(db, step.id)
    new_run_number = (last_run.run_number + 1) if last_run else 1

    new_run = StepRun(
        step_id=step.id,
        run_number=new_run_number,
        status=RunStatus.pending,
        command=last_run.command if last_run else None,
        worktree_path=last_run.worktree_path if last_run else None,
        cli_tool=last_run.cli_tool if last_run else None,
        timeout_secs=last_run.timeout_secs if last_run else None,
    )
    db.add(new_run)

    step.status = StepStatus.pending
    step.started_at = None
    step.completed_at = None

    # Unblock the work item if it was marked failed
    item = _get_item(db, project_id, item_id)
    if item.status == WorkItemStatus.failed:
        item.status = WorkItemStatus.in_progress

    _emit(db, "step_restarted", project_id, item_id, f"Step {step_id} restarted by user")
    db.commit()

    return _action_response(f"Step {step_id} queued for restart.", toast_type="success")


# ---------------------------------------------------------------------------
# Skip step
# ---------------------------------------------------------------------------


@router.post(
    "/item/{item_id}/skip-step/{step_id}",
    response_class=Response,
)
def skip_step(
    project_id: str,
    item_id: str,
    step_id: str,
    db: Session = Depends(get_db),
) -> Any:
    step = _get_step(db, project_id, item_id, step_id)

    if step.status not in (StepStatus.failed, StepStatus.needs_fix):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot skip: step status is '{step.status.value}' (must be failed or needs_fix)"
            ),
        )

    step.status = StepStatus.skipped
    step.completed_at = datetime.now(UTC)

    _emit(db, "step_skipped", project_id, item_id, f"Step {step_id} skipped by user")
    db.commit()

    return _action_response(f"Step {step_id} skipped.", toast_type="info")


# ---------------------------------------------------------------------------
# Restart from step N
# ---------------------------------------------------------------------------


@router.post(
    "/item/{item_id}/restart-from/{step_id}",
    response_class=Response,
)
def restart_from_step(
    project_id: str,
    item_id: str,
    step_id: str,
    db: Session = Depends(get_db),
) -> Any:
    # Find the target step to get its step_number
    first_step = _get_step(db, project_id, item_id, step_id)

    # Get all steps at or after this step_number
    downstream_steps = list(
        db.scalars(
            select(WorkflowStep)
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
                WorkflowStep.step_number >= first_step.step_number,
            )
            .order_by(WorkflowStep.step_number)
        ).all()
    )

    if not downstream_steps:
        raise HTTPException(status_code=404, detail="No steps found from this point")

    for step in downstream_steps:
        step.status = StepStatus.pending
        step.started_at = None
        step.completed_at = None

    # Create a new pending run for the first step
    last_run = _get_last_run(db, first_step.id)
    new_run_number = (last_run.run_number + 1) if last_run else 1
    new_run = StepRun(
        step_id=first_step.id,
        run_number=new_run_number,
        status=RunStatus.pending,
        command=last_run.command if last_run else None,
        worktree_path=last_run.worktree_path if last_run else None,
        cli_tool=last_run.cli_tool if last_run else None,
        timeout_secs=last_run.timeout_secs if last_run else None,
    )
    db.add(new_run)

    item = _get_item(db, project_id, item_id)
    item.status = WorkItemStatus.in_progress

    _emit(
        db,
        "step_restarted",
        project_id,
        item_id,
        f"Restarted from step {step_id} by user",
        {"from_step": step_id, "steps_reset": len(downstream_steps)},
    )
    db.commit()

    return _action_response(
        f"Restarting from step {step_id} ({len(downstream_steps)} steps reset).",
        toast_type="success",
    )


# ---------------------------------------------------------------------------
# Approve item
# ---------------------------------------------------------------------------


@router.post("/item/{item_id}/approve", response_class=Response)
def approve_item(
    project_id: str,
    item_id: str,
    db: Session = Depends(get_db),
) -> Any:
    item = _get_item(db, project_id, item_id)
    if item.status != WorkItemStatus.draft:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot approve: item status is '{item.status.value}' (must be draft)",
        )
    item.status = WorkItemStatus.approved
    _emit(db, "item_approved", project_id, item_id, f"Item {item_id} approved by user")
    db.commit()
    return _action_response(f"Item {item_id} approved.", toast_type="success", reload=True)


# ---------------------------------------------------------------------------
# Create batch from selection
# ---------------------------------------------------------------------------


@router.post("/batch/create-from-selection", response_class=Response)
async def create_batch_from_selection(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Create a new batch from a list of approved item IDs.

    Expects form data with one or more ``item_ids`` fields.
    """
    # Parse body — htmx sends application/x-www-form-urlencoded
    form = await request.form()
    item_ids = form.getlist("item_ids")

    if not item_ids:
        raise HTTPException(status_code=422, detail="No item IDs provided")

    # Verify all items exist and are approved
    items = list(
        db.scalars(
            select(WorkItem).where(
                WorkItem.project_id == project_id,
                WorkItem.id.in_(item_ids),
                WorkItem.status == WorkItemStatus.approved,
            )
        )
    )
    if not items:
        raise HTTPException(status_code=422, detail="No approved items found for the given IDs")

    # Allocate a batch ID
    from orch.db.models import IdSequence

    seq = db.scalar(
        select(IdSequence).where(
            IdSequence.project_id == project_id,
            IdSequence.prefix == "BATCH",
        )
    )
    if seq is None:
        seq = IdSequence(project_id=project_id, prefix="BATCH", next_number=1)
        db.add(seq)
        db.flush()
        batch_num = 1
    else:
        batch_num = seq.next_number
        seq.next_number += 1
    batch_id = f"BATCH-{batch_num:05d}"

    batch = Batch(
        project_id=project_id,
        id=batch_id,
        status=BatchStatus.planning,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
    )
    db.add(batch)
    db.flush()

    # Generate execution plan with dependency analysis
    from orch.batch_planner import (
        analyze_dependencies,
        generate_drawio,
        generate_execution_plan_md,
        generate_png,
    )
    from orch.db.models import WorkflowStep

    items_data = []
    for item in items:
        steps = list(
            db.scalars(
                select(WorkflowStep)
                .where(
                    WorkflowStep.project_id == project_id,
                    WorkflowStep.work_item_id == item.id,
                )
                .order_by(WorkflowStep.step_number)
            )
        )
        items_data.append(
            {
                "id": item.id,
                "title": item.title,
                "type": item.type.value,
                "depends_on": list(item.depends_on or []),
                "design_doc_content": item.design_doc_content,
                "steps": [
                    {"agent_label": s.agent_label, "step_type": s.step_type.value} for s in steps
                ],
            }
        )

    analysis = analyze_dependencies(items_data)
    batch.execution_plan_md = generate_execution_plan_md(batch_id, analysis, 4)
    batch.execution_plan_drawio = generate_drawio(batch_id, analysis, 4)
    batch.execution_plan_png = generate_png(batch_id, analysis, 4)

    for item in items:
        group = analysis[item.id].group if item.id in analysis else 0
        bi = BatchItem(
            project_id=project_id,
            batch_id=batch_id,
            work_item_id=item.id,
            execution_group=group,
            status=BatchItemStatus.pending,
        )
        db.add(bi)

    _emit(
        db,
        "batch_created",
        project_id,
        batch_id,
        f"Batch {batch_id} created with plan from {len(items)} items by user",
        {"item_ids": [i.id for i in items]},
    )
    db.commit()
    trigger = json.dumps(
        {
            "showToast": {
                "message": f"Batch {batch_id} created with {len(items)} items.",
                "type": "success",
            }
        }
    )
    return Response(
        status_code=204,
        headers={
            "HX-Trigger": trigger,
            "HX-Redirect": f"/project/{project_id}/batch/{batch_id}",
        },
    )


# ---------------------------------------------------------------------------
# Item-level confirm dialog (GET — returns HTML fragment)
# ---------------------------------------------------------------------------


@router.get(
    "/confirm-item/{action}/{item_id}",
    response_class=HTMLResponse,
)
def confirm_item_dialog(
    project_id: str,
    action: str,
    item_id: str,
    request: Request,
) -> Any:
    templates: Jinja2Templates = request.app.state.templates

    label_info = _ITEM_ACTION_LABELS.get(action)
    if label_info is None:
        raise HTTPException(status_code=400, detail=f"Unknown item action: {action}")

    title, description, confirm_label, danger = label_info

    action_url = f"/project/{project_id}/api/item/{item_id}/{action}"

    return templates.TemplateResponse(
        request,
        "fragments/confirm_action.html",
        {
            "title": f"{title.rstrip('?')} {item_id}?",
            "description": description,
            "confirm_url": action_url,
            "confirm_label": confirm_label,
            "danger": danger,
        },
    )


# ---------------------------------------------------------------------------
# Unapprove item (approved → draft)
# ---------------------------------------------------------------------------


@router.post("/item/{item_id}/unapprove", response_class=Response)
def unapprove_item(
    project_id: str,
    item_id: str,
    db: Session = Depends(get_db),
) -> Any:
    item = _get_item(db, project_id, item_id)
    if item.status != WorkItemStatus.approved:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot unapprove: item status is '{item.status.value}' (must be approved)",
        )
    item.status = WorkItemStatus.draft
    _emit(db, "item_unapproved", project_id, item_id, f"Item {item_id} unapproved by user")
    db.commit()
    return _action_response(f"Item {item_id} reverted to draft.", toast_type="info", reload=True)


# ---------------------------------------------------------------------------
# Restart item (failed → in_progress, reset all non-completed steps)
# ---------------------------------------------------------------------------


@router.post("/item/{item_id}/restart", response_class=Response)
def restart_item(
    project_id: str,
    item_id: str,
    db: Session = Depends(get_db),
) -> Any:
    item = _get_item(db, project_id, item_id)
    if item.status != WorkItemStatus.failed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot restart: item status is '{item.status.value}' (must be failed)",
        )

    # Find the first failed step and restart from there
    first_failed = db.scalar(
        select(WorkflowStep)
        .where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.status.in_([StepStatus.failed, StepStatus.needs_fix]),
        )
        .order_by(WorkflowStep.step_number)
        .limit(1)
    )

    # Check if all steps are still pending (failed before any step ran, e.g. worktree setup)
    all_pending = first_failed is None and all(
        s.status == StepStatus.pending
        for s in db.scalars(
            select(WorkflowStep).where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
        ).all()
    )

    if all_pending:
        # Failed at setup phase — reset item to approved so daemon retries it.
        # Also reset the batch item if it exists, and re-open the batch.
        item.status = WorkItemStatus.approved
        item.completed_at = None

        batch_item = db.scalar(
            select(BatchItem).where(
                BatchItem.project_id == project_id,
                BatchItem.work_item_id == item_id,
                BatchItem.status == BatchItemStatus.failed,
            )
        )
        if batch_item is not None:
            batch_item.status = BatchItemStatus.pending
            batch_item.notes = None
            batch_item.started_at = None
            # Re-open the parent batch so the daemon picks it up again
            batch = db.scalar(
                select(Batch).where(
                    Batch.project_id == project_id,
                    Batch.id == batch_item.batch_id,
                )
            )
            if batch is not None and batch.status == BatchStatus.completed_with_errors:
                batch.status = BatchStatus.approved
                batch.completed_at = None

        _emit(
            db,
            "item_restarted",
            project_id,
            item_id,
            f"Item {item_id} restarted (failed at setup, no steps ran)",
        )
        db.commit()

        return _action_response(
            f"Item {item_id} reset to approved — daemon will retry.",
            toast_type="success",
            reload=True,
        )

    if first_failed is None:
        raise HTTPException(status_code=422, detail="No failed steps found to restart")

    # Reset all steps from the first failed one onwards
    downstream = list(
        db.scalars(
            select(WorkflowStep)
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
                WorkflowStep.step_number >= first_failed.step_number,
            )
            .order_by(WorkflowStep.step_number)
        ).all()
    )

    for step in downstream:
        step.status = StepStatus.pending
        step.started_at = None
        step.completed_at = None

    # Create a new pending run for the first step
    last_run = _get_last_run(db, first_failed.id)
    new_run_number = (last_run.run_number + 1) if last_run else 1
    db.add(
        StepRun(
            step_id=first_failed.id,
            run_number=new_run_number,
            status=RunStatus.pending,
            command=last_run.command if last_run else None,
            worktree_path=last_run.worktree_path if last_run else None,
            cli_tool=last_run.cli_tool if last_run else None,
            timeout_secs=last_run.timeout_secs if last_run else None,
        )
    )

    item.status = WorkItemStatus.in_progress
    item.completed_at = None

    _emit(
        db,
        "item_restarted",
        project_id,
        item_id,
        f"Item {item_id} restarted by user from step {first_failed.step_id}",
        {"from_step": first_failed.step_id, "steps_reset": len(downstream)},
    )
    db.commit()

    return _action_response(
        f"Item {item_id} restarted from {first_failed.step_id} ({len(downstream)} steps reset).",
        toast_type="success",
        reload=True,
    )


# ---------------------------------------------------------------------------
# Pause item (in_progress → paused)
# ---------------------------------------------------------------------------


@router.post("/item/{item_id}/pause", response_class=Response)
def pause_item(
    project_id: str,
    item_id: str,
    db: Session = Depends(get_db),
) -> Any:
    item = _get_item(db, project_id, item_id)
    if item.status != WorkItemStatus.in_progress:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot pause: item status is '{item.status.value}' (must be in_progress)",
        )
    item.status = WorkItemStatus.paused
    _emit(db, "item_paused", project_id, item_id, f"Item {item_id} paused by user")
    db.commit()
    return _action_response(f"Item {item_id} paused.", toast_type="warning", reload=True)


# ---------------------------------------------------------------------------
# Resume item (paused → in_progress)
# ---------------------------------------------------------------------------


@router.post("/item/{item_id}/resume", response_class=Response)
def resume_item(
    project_id: str,
    item_id: str,
    db: Session = Depends(get_db),
) -> Any:
    item = _get_item(db, project_id, item_id)
    if item.status != WorkItemStatus.paused:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot resume: item status is '{item.status.value}' (must be paused)",
        )
    item.status = WorkItemStatus.in_progress
    _emit(db, "item_resumed", project_id, item_id, f"Item {item_id} resumed by user")
    db.commit()
    return _action_response(f"Item {item_id} resumed.", toast_type="success", reload=True)


# ---------------------------------------------------------------------------
# Batch-level action labels
# ---------------------------------------------------------------------------

_BATCH_ACTION_LABELS: dict[str, tuple[str, str, str, bool]] = {
    "approve": (
        "Approve batch?",
        "This approves the batch for execution. The daemon will pick it up on its next poll.",
        "Approve",
        False,
    ),
    "pause": (
        "Pause batch?",
        "In-progress items will finish, but no new items will be launched.",
        "Pause",
        True,
    ),
    "resume": (
        "Resume batch?",
        "Resumes launching pending items from where it was paused.",
        "Resume",
        False,
    ),
    "cancel": (
        "Cancel batch?",
        "Cancels this batch. It will no longer be eligible for execution.",
        "Cancel",
        True,
    ),
}


# ---------------------------------------------------------------------------
# Batch confirm dialog (GET — returns HTML fragment)
# ---------------------------------------------------------------------------


@router.get(
    "/confirm-batch/{action}/{batch_id}",
    response_class=HTMLResponse,
)
def confirm_batch_dialog(
    project_id: str,
    action: str,
    batch_id: str,
    request: Request,
) -> Any:
    templates: Jinja2Templates = request.app.state.templates

    label_info = _BATCH_ACTION_LABELS.get(action)
    if label_info is None:
        raise HTTPException(status_code=400, detail=f"Unknown batch action: {action}")

    title, description, confirm_label, danger = label_info

    action_url = f"/project/{project_id}/api/batch/{batch_id}/{action}"

    return templates.TemplateResponse(
        request,
        "fragments/confirm_action.html",
        {
            "title": f"{title.rstrip('?')} {batch_id}?",
            "description": description,
            "confirm_url": action_url,
            "confirm_label": confirm_label,
            "danger": danger,
        },
    )


# ---------------------------------------------------------------------------
# Approve batch (planning → approved)
# ---------------------------------------------------------------------------


def _get_batch(db: Session, project_id: str, batch_id: str) -> Batch:
    batch = db.scalar(
        select(Batch).where(
            Batch.project_id == project_id,
            Batch.id == batch_id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
    return batch


@router.post("/batch/{batch_id}/approve", response_class=Response)
def approve_batch(
    project_id: str,
    batch_id: str,
    db: Session = Depends(get_db),
) -> Any:
    batch = _get_batch(db, project_id, batch_id)
    if batch.status != BatchStatus.planning:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot approve: batch status is '{batch.status.value}' (must be planning)",
        )
    batch.status = BatchStatus.approved
    batch.updated_at = datetime.now(UTC)
    _emit(db, "batch_approved", project_id, batch_id, f"Batch {batch_id} approved by user")
    db.commit()
    return _action_response(f"Batch {batch_id} approved.", toast_type="success", reload=True)


# ---------------------------------------------------------------------------
# Pause batch (executing → paused)
# ---------------------------------------------------------------------------


@router.post("/batch/{batch_id}/pause", response_class=Response)
def pause_batch(
    project_id: str,
    batch_id: str,
    db: Session = Depends(get_db),
) -> Any:
    batch = _get_batch(db, project_id, batch_id)
    if batch.status != BatchStatus.executing:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot pause: batch status is '{batch.status.value}' (must be executing)",
        )
    batch.status = BatchStatus.paused
    batch.updated_at = datetime.now(UTC)
    _emit(db, "batch_paused", project_id, batch_id, f"Batch {batch_id} paused by user")
    db.commit()
    return _action_response(f"Batch {batch_id} paused.", toast_type="warning", reload=True)


# ---------------------------------------------------------------------------
# Resume batch (paused → executing)
# ---------------------------------------------------------------------------


@router.post("/batch/{batch_id}/resume", response_class=Response)
def resume_batch(
    project_id: str,
    batch_id: str,
    db: Session = Depends(get_db),
) -> Any:
    batch = _get_batch(db, project_id, batch_id)
    if batch.status != BatchStatus.paused:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot resume: batch status is '{batch.status.value}' (must be paused)",
        )
    batch.status = BatchStatus.executing
    batch.updated_at = datetime.now(UTC)
    _emit(db, "batch_resumed", project_id, batch_id, f"Batch {batch_id} resumed by user")
    db.commit()
    return _action_response(f"Batch {batch_id} resumed.", toast_type="success", reload=True)


# ---------------------------------------------------------------------------
# Cancel batch (planning/approved → cancelled)
# ---------------------------------------------------------------------------


@router.post("/batch/{batch_id}/cancel", response_class=Response)
def cancel_batch(
    project_id: str,
    batch_id: str,
    db: Session = Depends(get_db),
) -> Any:
    batch = _get_batch(db, project_id, batch_id)
    if batch.status not in (BatchStatus.planning, BatchStatus.approved):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot cancel: batch status is '{batch.status.value}'"
                " (must be planning or approved)"
            ),
        )
    batch.status = BatchStatus.cancelled
    batch.updated_at = datetime.now(UTC)
    _emit(db, "batch_cancelled", project_id, batch_id, f"Batch {batch_id} cancelled by user")
    db.commit()
    return _action_response(f"Batch {batch_id} cancelled.", toast_type="warning", reload=True)
