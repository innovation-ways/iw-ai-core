"""Work item management CLI commands: register, approve, unapprove, archive, item-status."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
from sqlalchemy import select

from orch.archive import archive_all_completed, archive_work_item
from orch.cli.utils import TYPE_TO_ID_PREFIX, output_error, resolve_project, validate_id_prefix
from orch.db.models import (
    Batch,
    BatchItem,
    BatchStatus,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

# ---------------------------------------------------------------------------
# Pure validation helpers (used by unit tests without DB)
# ---------------------------------------------------------------------------


def validate_approve_transition(current_status: WorkItemStatus) -> str | None:
    """Return an error message if approve is invalid, or None if OK."""
    if current_status != WorkItemStatus.draft:
        return f"Cannot approve: current status is '{current_status.value}'"
    return None


def validate_unapprove_transition(
    current_status: WorkItemStatus,
    active_batch_id: str | None,
) -> str | None:
    """Return an error message if unapprove is invalid, or None if OK."""
    if current_status != WorkItemStatus.approved:
        return f"Cannot unapprove: current status is '{current_status.value}'"
    if active_batch_id:
        return f"Cannot unapprove: item is in batch {active_batch_id}"
    return None


# ---------------------------------------------------------------------------
# Agent → StepType inference for workflow manifests
# ---------------------------------------------------------------------------

# Ordered longest-match first so "code-review-fix-final" beats "code-review"
_AGENT_STEP_TYPE_PATTERNS: list[tuple[str, StepType]] = [
    ("code-review-fix-final", StepType.code_review_fix_final),
    ("code-review-final", StepType.code_review_final),
    ("code-review-fix", StepType.code_review_fix),
    ("code-review", StepType.code_review),
    ("backend-review", StepType.code_review),
    ("api-review", StepType.code_review),
    ("frontend-review", StepType.code_review),
    ("tests-review", StepType.code_review),
    ("database-review", StepType.code_review),
    ("pipeline-review", StepType.code_review),
    ("template-review", StepType.code_review),
    ("quality-validation", StepType.quality_validation),
    ("qv-gate", StepType.quality_validation),
    ("qv-fix", StepType.qv_fix),
    ("qv-browser", StepType.browser_verification),
    ("browser-verification", StepType.browser_verification),
]


def agent_to_step_type(agent: str) -> StepType:
    """Infer StepType from agent name slug. Defaults to implementation."""
    for pattern, step_type in _AGENT_STEP_TYPE_PATTERNS:
        if pattern in agent:
            return step_type
    return StepType.implementation


def agent_to_label(agent: str) -> str:
    """Convert agent slug to CamelCase label (strips trailing -impl)."""
    cleaned = agent.replace("-impl", "")
    return "".join(part.capitalize() for part in cleaned.split("-"))


# ---------------------------------------------------------------------------
# Manifest parsing
# ---------------------------------------------------------------------------


def parse_manifest_steps(manifest_path: Path) -> list[dict[str, Any]]:
    """Parse a workflow-manifest.json and return the steps list."""
    data: Any = json.loads(manifest_path.read_text())
    steps: list[Any] = data.get("steps", [])
    return [dict(s) for s in steps]


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

_ITEM_TYPE_MAP: dict[str, WorkItemType] = {
    "feature": WorkItemType.Feature,
    "incident": WorkItemType.Issue,
    "cr": WorkItemType.ChangeRequest,
    "research": WorkItemType.Research,
}

_ACTIVE_BATCH_STATUSES: list[BatchStatus] = [
    BatchStatus.planning,
    BatchStatus.approved,
    BatchStatus.executing,
    BatchStatus.paused,
    BatchStatus.blocked,
    BatchStatus.publishing,
    BatchStatus.publish_failed,
]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@click.command("register")
@click.argument("item_id")
@click.argument("title")
@click.option(
    "--type",
    "item_type",
    required=True,
    type=click.Choice(["feature", "incident", "cr", "research"]),
    help="Work item type",
)
@click.option("--design-doc", default=None, help="Relative path to design document")
@click.option("--steps-from", default=None, help="Path to workflow-manifest.json")
@click.pass_context
def register(
    ctx: click.Context,
    item_id: str,
    title: str,
    item_type: str,
    design_doc: str | None,
    steps_from: str | None,
) -> None:
    """Register a new work item in the database (idempotent)."""
    if not validate_id_prefix(item_id, item_type):
        expected = TYPE_TO_ID_PREFIX.get(item_type, "?")
        output_error(
            ctx,
            f"ID '{item_id}' does not match expected prefix '{expected}' for type '{item_type}'",
            2,
        )

    project_id = resolve_project(ctx)

    # Pre-parse manifest steps (fail fast before touching DB)
    manifest_steps: list[dict[str, Any]] = []
    if steps_from:
        manifest_path = Path(steps_from)
        if not manifest_path.exists():
            output_error(ctx, f"Manifest file not found: {steps_from}", 2)
        try:
            manifest_steps = parse_manifest_steps(manifest_path)
        except (json.JSONDecodeError, OSError) as exc:
            output_error(ctx, f"Invalid manifest file: {exc}", 2)

    get_session = ctx.obj["get_session"]
    try:
        with get_session() as session:
            # Idempotency check
            existing = session.get(WorkItem, (project_id, item_id))
            if existing is not None:
                if ctx.obj.get("json"):
                    click.echo(
                        json.dumps(
                            {
                                "project_id": project_id,
                                "id": item_id,
                                "status": existing.status.value,
                                "created": False,
                                "message": "Already registered",
                            }
                        )
                    )
                else:
                    click.echo(
                        f"Already registered {item_id}: {existing.title} [{existing.status.value}]"
                    )
                return

            # Load the design doc content from disk so downstream consumers
            # (batch planner file-overlap detection, FTS, dashboard preview)
            # have the full text — not just a path. Resolved relative to the
            # current working directory, which by convention is the project
            # repo root when `iw register` is invoked from the
            # iw-new-* skills. Missing files are tolerated with a warning so
            # that registration stays idempotent when the doc lives outside
            # the checkout (e.g. planned items).
            design_doc_content: str | None = None
            if design_doc:
                doc_path = Path(design_doc)
                if not doc_path.is_absolute():
                    doc_path = Path.cwd() / doc_path
                try:
                    design_doc_content = doc_path.read_text(encoding="utf-8")
                except FileNotFoundError:
                    click.echo(
                        f"Warning: design doc not found at {doc_path} — "
                        "item will be registered without content (batch planner "
                        "file-overlap detection will not see this item's files)",
                        err=True,
                    )
                except OSError as exc:
                    click.echo(
                        f"Warning: could not read design doc {doc_path}: {exc}",
                        err=True,
                    )

            # Insert work item
            work_item = WorkItem(
                project_id=project_id,
                id=item_id,
                type=_ITEM_TYPE_MAP[item_type],
                title=title,
                design_doc_path=design_doc,
                design_doc_content=design_doc_content,
                status=WorkItemStatus.draft,
                phase=WorkItemPhase.active,
                config={},
                depends_on=[],
                blocks=[],
            )
            session.add(work_item)
            session.flush()

            # Insert workflow steps from manifest
            for idx, step_data in enumerate(manifest_steps):
                step_id_str = str(step_data.get("step", f"S{idx + 1:02d}"))
                agent = str(step_data.get("agent", ""))

                # Explicit step_type overrides inference
                step_type_raw = step_data.get("step_type")
                if isinstance(step_type_raw, str):
                    try:
                        step_type: StepType = StepType(step_type_raw)
                    except ValueError:
                        step_type = agent_to_step_type(agent)
                else:
                    step_type = agent_to_step_type(agent)

                # Explicit agent_label overrides derivation
                label_raw = step_data.get("agent_label")
                label = str(label_raw) if label_raw else agent_to_label(agent) or step_id_str

                description_raw = step_data.get("description")
                description = str(description_raw) if description_raw else None

                label_raw_val = step_data.get("step_label")
                step_label = str(label_raw_val) if label_raw_val else None

                # Derive numeric step_number from step_id ("S01" → 1)
                num_str = step_id_str.lstrip("Ss")
                try:
                    step_number = int(num_str)
                except ValueError:
                    step_number = idx + 1

                session.add(
                    WorkflowStep(
                        project_id=project_id,
                        work_item_id=item_id,
                        step_number=step_number,
                        step_id=step_id_str,
                        agent_label=label,
                        opencode_agent=agent or None,
                        step_type=step_type,
                        step_label=step_label,
                        description=description,
                    )
                )

            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "project_id": project_id,
                    "id": item_id,
                    "title": title,
                    "status": "draft",
                    "created": True,
                }
            )
        )
    else:
        click.echo(f"Registered {item_id}: {title} [draft]")


@click.command("approve")
@click.argument("item_id")
@click.pass_context
def approve(ctx: click.Context, item_id: str) -> None:
    """Approve a work item for execution (draft → approved)."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            item = session.get(WorkItem, (project_id, item_id))
            if item is None:
                output_error(ctx, f"Work item {item_id} not found in project {project_id}", 1)

            error = validate_approve_transition(item.status)
            if error:
                output_error(ctx, error, 1)

            item.status = WorkItemStatus.approved
            item.updated_at = datetime.now(UTC)
            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps({"project_id": project_id, "id": item_id, "status": "approved"}))
    else:
        click.echo(f"Approved {item_id}")


@click.command("unapprove")
@click.argument("item_id")
@click.pass_context
def unapprove(ctx: click.Context, item_id: str) -> None:
    """Revert an approved work item back to draft (approved → draft)."""
    from sqlalchemy import select

    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            item = session.get(WorkItem, (project_id, item_id))
            if item is None:
                output_error(ctx, f"Work item {item_id} not found in project {project_id}", 1)

            # Detect active batch membership
            active_batch_item = session.execute(
                select(BatchItem)
                .join(
                    Batch,
                    (BatchItem.project_id == Batch.project_id) & (BatchItem.batch_id == Batch.id),
                )
                .where(
                    BatchItem.project_id == project_id,
                    BatchItem.work_item_id == item_id,
                    Batch.status.in_(_ACTIVE_BATCH_STATUSES),
                )
            ).scalar_one_or_none()

            active_batch_id: str | None = (
                active_batch_item.batch_id if active_batch_item is not None else None
            )

            error = validate_unapprove_transition(item.status, active_batch_id)
            if error:
                exit_code = 4 if active_batch_id else 1
                output_error(ctx, error, exit_code)

            item.status = WorkItemStatus.draft
            item.updated_at = datetime.now(UTC)
            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps({"project_id": project_id, "id": item_id, "status": "draft"}))
    else:
        click.echo(f"Unapproved {item_id}")


@click.command("archive")
@click.argument("item_id", required=False, default=None)
@click.option("--all-completed", is_flag=True, help="Archive all completed items in the project")
@click.option(
    "--no-cleanup",
    is_flag=True,
    help="Store in DB but do not delete active files from project repo",
)
@click.option(
    "--archive-dir",
    envvar="IW_CORE_ARCHIVE_DIR",
    default=None,
    help="Directory for compressed archives (defaults to IW_CORE_ARCHIVE_DIR env var)",
)
@click.pass_context
def archive(
    ctx: click.Context,
    item_id: str | None,
    all_completed: bool,
    no_cleanup: bool,
    archive_dir: str | None,
) -> None:
    """Archive completed work items (Tier 1 DB + Tier 2 .tar.zst compression)."""
    if not item_id and not all_completed:
        output_error(ctx, "Provide an item ID or use --all-completed", 2)
    if item_id and all_completed:
        output_error(ctx, "Cannot specify both an item ID and --all-completed", 2)

    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]
    cleanup = not no_cleanup

    try:
        with get_session() as session:
            if all_completed:
                archived_ids = archive_all_completed(session, project_id, archive_dir)
            else:
                if item_id is None:
                    output_error(ctx, "Provide an item ID or use --all-completed", 2)
                archive_work_item(session, project_id, item_id, archive_dir, cleanup=cleanup)
                archived_ids = [item_id]

    except ValueError as exc:
        output_error(ctx, str(exc), 1)
    except Exception as exc:
        output_error(ctx, f"Archive error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {"project_id": project_id, "archived": archived_ids, "count": len(archived_ids)}
            )
        )
    else:
        for aid in archived_ids:
            click.echo(f"Archived {aid}")


@click.command("item-status")
@click.argument("item_id")
@click.option("--json", "-j", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def item_status(ctx: click.Context, item_id: str, json_output: bool) -> None:
    """Show the current status of a work item."""
    if json_output:
        ctx.obj["json"] = True
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    result: dict[str, Any] = {}

    try:
        with get_session() as session:
            item = session.get(WorkItem, (project_id, item_id))
            if item is None:
                output_error(ctx, f"Work item {item_id} not found in project {project_id}", 1)

            steps = (
                session.execute(
                    select(WorkflowStep)
                    .where(
                        WorkflowStep.project_id == project_id,
                        WorkflowStep.work_item_id == item_id,
                    )
                    .order_by(WorkflowStep.step_number)
                )
                .scalars()
                .all()
            )

            total_steps = len(steps)
            completed_steps = sum(1 for s in steps if s.status == StepStatus.completed)

            current_step: dict[str, Any] | None = None
            for s in steps:
                if s.status == StepStatus.in_progress:
                    duration_str = None
                    if s.started_at:
                        secs = int(
                            (datetime.now(UTC) - s.started_at.replace(tzinfo=UTC)).total_seconds()
                        )
                        duration_str = f"{secs // 60}m {secs % 60}s"
                    current_step = {
                        "step_id": s.step_id,
                        "label": s.agent_label,
                        "status": s.status.value,
                        "duration": duration_str,
                    }
                    break

            # Find active batch membership
            active_batch_item = session.execute(
                select(BatchItem)
                .join(
                    Batch,
                    (BatchItem.project_id == Batch.project_id) & (BatchItem.batch_id == Batch.id),
                )
                .where(
                    BatchItem.project_id == project_id,
                    BatchItem.work_item_id == item_id,
                )
                .order_by(Batch.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            batch_id: str | None = active_batch_item.batch_id if active_batch_item else None
            worktree: str | None = None
            if active_batch_item and isinstance(active_batch_item.worktree_info, dict):
                worktree = active_batch_item.worktree_info.get("path")

            result = {
                "project_id": project_id,
                "id": item_id,
                "title": item.title,
                "status": item.status.value,
                "phase": item.phase.value,
                "total_steps": total_steps,
                "completed_steps": completed_steps,
                "current_step": current_step,
                "batch_id": batch_id,
                "worktree": worktree,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
                "steps": [
                    {
                        "step_id": s.step_id,
                        "label": s.agent_label,
                        "type": s.step_type.value,
                        "status": s.status.value,
                    }
                    for s in steps
                ],
            }

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps(result))
    else:
        click.echo(f"{item_id}: {result['title']}")
        click.echo(f"  Status: {result['status']} | Phase: {result['phase']}")
        step_info = f"{result['completed_steps']}/{result['total_steps']} completed"
        if result.get("current_step"):
            cs = result["current_step"]
            dur = f", {cs['duration']}" if cs.get("duration") else ""
            step_info += f" | Current: {cs['step_id']} {cs['label']} ({cs['status']}{dur})"
        click.echo(f"  Steps: {step_info}")
        batch_str = result.get("batch_id") or "—"
        wt_str = result.get("worktree") or "—"
        click.echo(f"  Batch: {batch_str} | Worktree: {wt_str}")
        created = (result.get("created_at") or "")[:16]
        updated = (result.get("updated_at") or "")[:16]
        click.echo(f"  Created: {created} | Updated: {updated}")
