"""Step lifecycle CLI commands: step-start, step-done, step-fail, step-restart, etc."""

from __future__ import annotations

import json
import os
import signal
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
from sqlalchemy import select

from orch.cli.utils import output_error, resolve_project
from orch.db.models import (
    DaemonEvent,
    RunStatus,
    StepRun,
    StepStatus,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
)
from orch.utils.log_capture import capture_log_content

# ---------------------------------------------------------------------------
# Pure validation helpers (used by unit tests without DB)
# ---------------------------------------------------------------------------


def validate_step_start_transition(current_status: StepStatus) -> tuple[str | None, bool]:
    """Return (error_message, already_started) for step-start validation.

    Returns (None, False) if step is pending and can be started.
    Returns (None, True) if step is already in_progress (idempotent — no-op).
    Returns (error_msg, False) for invalid transitions.
    """
    if current_status == StepStatus.pending:
        return None, False
    if current_status == StepStatus.in_progress:
        return None, True  # Idempotent: daemon already started it
    return f"Cannot start step: current status is '{current_status.value}'", False


def validate_step_done_transition(current_status: StepStatus) -> str | None:
    """Return an error message if step-done is invalid, or None if OK."""
    if current_status != StepStatus.in_progress:
        return f"Cannot mark done: current status is '{current_status.value}'"
    return None


def validate_step_fail_transition(current_status: StepStatus) -> str | None:
    """Return an error message if step-fail is invalid, or None if OK."""
    if current_status != StepStatus.in_progress:
        return f"Cannot fail step: current status is '{current_status.value}'"
    return None


_RESTARTABLE_STATUSES = frozenset({StepStatus.failed, StepStatus.needs_fix})


def validate_step_restart_transition(current_status: StepStatus) -> str | None:
    """Return an error message if step-restart is invalid, or None if OK."""
    if current_status not in _RESTARTABLE_STATUSES:
        return (
            f"Cannot restart step: current status is '{current_status.value}'"
            " (must be failed or needs_fix)"
        )
    return None


def validate_step_skip_transition(current_status: StepStatus) -> str | None:
    """Return an error message if step-skip is invalid, or None if OK."""
    if current_status != StepStatus.failed:
        return f"Cannot skip step: current status is '{current_status.value}' (must be failed)"
    return None


_KILLABLE_RUN_STATUSES = frozenset({RunStatus.running, RunStatus.stalled})


def validate_step_kill_transition(current_status: StepStatus) -> str | None:
    """Return an error message if step-kill is invalid, or None if OK."""
    if current_status != StepStatus.in_progress:
        return f"Cannot kill step: current status is '{current_status.value}' (must be in_progress)"
    return None


# ---------------------------------------------------------------------------
# Shared helper: look up a step by string step_id
# ---------------------------------------------------------------------------


def _find_step(
    session: Any,
    project_id: str,
    item_id: str,
    step_id: str,
) -> WorkflowStep | None:
    return session.execute(  # type: ignore[no-any-return]
        select(WorkflowStep).where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.step_id == step_id,
        )
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Browser verification teardown helper
# ---------------------------------------------------------------------------


def _run_browser_teardown_if_needed(
    project_id: str,
    item_id: str,
    step_id: str,
    step_type: Any,
    worktree_path: str,
) -> None:
    """Run browser env teardown when a browser_verification step ends (any terminal state).

    Loads the project config from the projects.toml path stored in DaemonConfig.
    Silently skips if the config cannot be loaded or if the project is not
    browser_verification-enabled (opt-in behaviour).
    """
    try:
        from orch.daemon import browser_env  # noqa: PLC0415

        if not browser_env.is_browser_verification_step(step_type):
            return

        # Load project config — available via projects_toml in DaemonConfig
        from orch.config import load_config  # noqa: PLC0415
        from orch.daemon.project_registry import load_projects_toml  # noqa: PLC0415

        try:
            daemon_cfg = load_config()
            projects = load_projects_toml(daemon_cfg.projects_toml)
        except Exception:
            return  # Config unavailable (test environment or misconfiguration) — skip

        project_config = projects.get(project_id)
        if project_config is None:
            return

        bv_env = browser_env.resolve_browser_env(
            project_config, project_id, item_id, worktree_path=worktree_path
        )
        if bv_env is None:
            return

        browser_env.run_env_down_hook(
            project_config,
            worktree_path,
            bv_env,
            item_id,
            step_id,
        )
    except Exception:
        import logging  # noqa: PLC0415

        logging.getLogger(__name__).warning(
            "browser env teardown failed for %s/%s (non-fatal)",
            item_id,
            step_id,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@click.command("step-start")
@click.argument("item_id")
@click.option("--step", "step_id", required=True, help="Step ID (e.g., S01)")
@click.pass_context
def step_start(ctx: click.Context, item_id: str, step_id: str) -> None:
    """Mark a workflow step as started (pending → in_progress)."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    already_started = False

    try:
        with get_session() as session:
            step = _find_step(session, project_id, item_id, step_id)
            if step is None:
                output_error(
                    ctx,
                    f"Step {step_id} not found for item {item_id} in project {project_id}",
                    1,
                )

            error, already_started = validate_step_start_transition(step.status)
            if error:
                output_error(ctx, error, 1)

            if not already_started:
                step.status = StepStatus.in_progress
                step.started_at = datetime.now(UTC)

                # Transition work item approved → in_progress on first step start
                work_item = session.scalar(
                    select(WorkItem).where(
                        WorkItem.project_id == project_id,
                        WorkItem.id == item_id,
                    )
                )
                if work_item and work_item.status == WorkItemStatus.approved:
                    work_item.status = WorkItemStatus.in_progress

                session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "project_id": project_id,
                    "item_id": item_id,
                    "step_id": step_id,
                    "status": "in_progress",
                    "already_started": already_started,
                }
            )
        )
    else:
        suffix = " (already in progress)" if already_started else ""
        click.echo(f"Started {item_id} step {step_id}{suffix}")


@click.command("step-done")
@click.argument("item_id")
@click.option("--step", "step_id", required=True, help="Step ID (e.g., S01)")
@click.option("--report", "report_path", default=None, help="Relative path to the report file")
@click.pass_context
def step_done(ctx: click.Context, item_id: str, step_id: str, report_path: str | None) -> None:
    """Mark a workflow step as completed (in_progress → completed)."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    _worktree_path: str = ""
    _step_type_val: Any = None

    try:
        with get_session() as session:
            step = _find_step(session, project_id, item_id, step_id)
            if step is None:
                output_error(
                    ctx,
                    f"Step {step_id} not found for item {item_id} in project {project_id}",
                    1,
                )

            error = validate_step_done_transition(step.status)
            if error:
                output_error(ctx, error, 1)

            step.status = StepStatus.completed
            step.completed_at = datetime.now(UTC)
            if report_path is not None:
                step.report_file = report_path
                # Read file content for immediate dashboard rendering (Tier 1)
                full_path = Path(report_path)
                if not full_path.is_absolute():
                    full_path = Path.cwd() / full_path
                if full_path.exists():
                    step.report_content = full_path.read_text(encoding="utf-8")

            # Capture log content into DB before the worktree is cleaned up
            step_run = session.execute(
                select(StepRun)
                .where(
                    StepRun.step_id == step.id,
                    StepRun.status == RunStatus.running,
                )
                .order_by(StepRun.run_number.desc())
                .limit(1)
            ).scalar_one_or_none()
            if step_run is not None:
                step_run.status = RunStatus.completed
                step_run.completed_at = datetime.now(UTC)
                if step_run.started_at is not None:
                    step_run.duration_secs = (
                        step_run.completed_at - step_run.started_at
                    ).total_seconds()
                capture_log_content(step_run)
                _worktree_path = step_run.worktree_path or ""
            _step_type_val = step.step_type

            session.add(
                DaemonEvent(
                    project_id=project_id,
                    event_type="step_completed",
                    entity_id=item_id,
                    entity_type="work_item",
                    message=f"Step {step_id} completed",
                    event_metadata={"step_id": step_id},
                )
            )
            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    # browser_verification teardown — runs after DB flush, outside the session
    _run_browser_teardown_if_needed(project_id, item_id, step_id, _step_type_val, _worktree_path)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "project_id": project_id,
                    "item_id": item_id,
                    "step_id": step_id,
                    "status": "completed",
                    "report_file": report_path,
                }
            )
        )
    else:
        click.echo(f"Completed {item_id} step {step_id}")


@click.command("step-fail")
@click.argument("item_id")
@click.option("--step", "step_id", required=True, help="Step ID (e.g., S01)")
@click.option("--reason", required=True, help="Human-readable failure reason")
@click.option(
    "--report",
    "report_path",
    default=None,
    help=(
        "Relative path to the failure report file. Required for browser_verification "
        "steps so the fix-cycle agent sees the full V-table and root-cause section."
    ),
)
@click.pass_context
def step_fail(
    ctx: click.Context,
    item_id: str,
    step_id: str,
    reason: str,
    report_path: str | None,
) -> None:
    """Mark a workflow step as failed (in_progress → failed)."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    _worktree_path: str = ""
    _step_type_val: Any = None

    try:
        with get_session() as session:
            step = _find_step(session, project_id, item_id, step_id)
            if step is None:
                output_error(
                    ctx,
                    f"Step {step_id} not found for item {item_id} in project {project_id}",
                    1,
                )

            error = validate_step_fail_transition(step.status)
            if error:
                output_error(ctx, error, 1)

            step.status = StepStatus.failed
            _step_type_val = step.step_type
            if report_path is not None:
                step.report_file = report_path
                # Read file content for fix-cycle prompt assembly (Tier 1)
                full_path = Path(report_path)
                if not full_path.is_absolute():
                    full_path = Path.cwd() / full_path
                if full_path.exists():
                    step.report_content = full_path.read_text(encoding="utf-8")
            session.flush()

            # Store reason in the current running step_run (if daemon created one)
            step_run = session.execute(
                select(StepRun)
                .where(
                    StepRun.step_id == step.id,
                    StepRun.status == RunStatus.running,
                )
                .order_by(StepRun.run_number.desc())
                .limit(1)
            ).scalar_one_or_none()

            if step_run is not None:
                step_run.error_message = reason
                step_run.status = RunStatus.failed
                step_run.completed_at = datetime.now(UTC)
                if report_path is not None:
                    step_run.report_file = report_path
                capture_log_content(step_run)
                _worktree_path = step_run.worktree_path or ""

            session.add(
                DaemonEvent(
                    project_id=project_id,
                    event_type="step_failed",
                    entity_id=item_id,
                    entity_type="work_item",
                    message=f"Step {step_id} failed: {reason}",
                    event_metadata={"step_id": step_id, "reason": reason},
                )
            )
            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    # browser_verification teardown — runs after DB flush, outside the session
    _run_browser_teardown_if_needed(project_id, item_id, step_id, _step_type_val, _worktree_path)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "project_id": project_id,
                    "item_id": item_id,
                    "step_id": step_id,
                    "status": "failed",
                    "reason": reason,
                    "report_file": report_path,
                }
            )
        )
    else:
        click.echo(f"Failed {item_id} step {step_id}: {reason}")


# ---------------------------------------------------------------------------
# step-restart: retry a failed/needs_fix step (creates a new StepRun)
# ---------------------------------------------------------------------------


@click.command("step-restart")
@click.argument("item_id")
@click.option("--step", "step_id", required=True, help="Step ID (e.g., S01)")
@click.pass_context
def step_restart(ctx: click.Context, item_id: str, step_id: str) -> None:
    """Restart a failed step: reset to pending so the daemon relaunches it."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]
    next_run_number: int | None = None

    try:
        with get_session() as session:
            step = _find_step(session, project_id, item_id, step_id)
            if step is None:
                output_error(
                    ctx,
                    f"Step {step_id} not found for item {item_id} in project {project_id}",
                    1,
                )

            error = validate_step_restart_transition(step.status)
            if error:
                output_error(ctx, error, 1)

            # Guard: refuse if any subsequent step has already been started or completed.
            # Restarting S15 after S16 has run would corrupt the workflow state.
            non_pristine = (
                StepStatus.in_progress,
                StepStatus.completed,
                StepStatus.failed,
                StepStatus.needs_fix,
            )
            advanced = session.execute(
                select(WorkflowStep)
                .where(
                    WorkflowStep.project_id == project_id,
                    WorkflowStep.work_item_id == item_id,
                    WorkflowStep.step_number > step.step_number,
                    WorkflowStep.status.in_(non_pristine),
                )
                .order_by(WorkflowStep.step_number)
                .limit(1)
            ).scalar_one_or_none()
            if advanced is not None:
                output_error(
                    ctx,
                    f"Cannot restart {step_id}: subsequent step {advanced.step_id} "
                    f"is already in state '{advanced.status.value}'. "
                    "Reset or skip later steps first.",
                    1,
                )

            # Reset step to pending — the daemon's _launch_step will create a
            # fresh running StepRun when it picks this step up on the next poll.
            # We do NOT create a pending StepRun here to avoid orphan rows.
            step.status = StepStatus.pending
            step.started_at = None
            step.completed_at = None

            # Compute next_run_number for the output message (not persisted)
            max_run = session.execute(
                select(StepRun.run_number)
                .where(StepRun.step_id == step.id)
                .order_by(StepRun.run_number.desc())
                .limit(1)
            ).scalar_one_or_none()
            next_run_number = (max_run or 0) + 1

            # If the work item itself is failed, reset it to in_progress
            work_item = session.execute(
                select(WorkItem).where(
                    WorkItem.project_id == project_id,
                    WorkItem.id == item_id,
                )
            ).scalar_one_or_none()

            if work_item and work_item.status == WorkItemStatus.failed:
                work_item.status = WorkItemStatus.in_progress

            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "project_id": project_id,
                    "item_id": item_id,
                    "step_id": step_id,
                    "status": "pending",
                    "next_run_number": next_run_number,
                }
            )
        )
    else:
        click.echo(f"Restarted {item_id} step {step_id} (next run will be #{next_run_number})")


# ---------------------------------------------------------------------------
# step-restart-from: reset a step and all subsequent steps to pending
# ---------------------------------------------------------------------------


@click.command("step-restart-from")
@click.argument("item_id")
@click.option("--step", "step_id", required=True, help="Step ID to restart from (e.g., S01)")
@click.pass_context
def step_restart_from(ctx: click.Context, item_id: str, step_id: str) -> None:
    """Reset a step and all subsequent steps to pending."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]
    reset_step_ids: list[str] = []

    try:
        with get_session() as session:
            step = _find_step(session, project_id, item_id, step_id)
            if step is None:
                output_error(
                    ctx,
                    f"Step {step_id} not found for item {item_id} in project {project_id}",
                    1,
                )

            # The target step must be in a non-terminal restartable state
            if step.status in (StepStatus.completed, StepStatus.skipped):
                # Allow restarting from completed steps too — they go back to pending
                pass
            elif step.status == StepStatus.pending:
                output_error(ctx, "Step is already pending", 1)
            elif step.status == StepStatus.in_progress:
                output_error(
                    ctx,
                    "Cannot restart from an in-progress step (use step-kill first)",
                    1,
                )

            # Get all steps for this item, ordered by step_number
            all_steps = (
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

            # Reset the target step and all subsequent steps
            for s in all_steps:
                if s.step_number >= step.step_number:
                    if s.status == StepStatus.in_progress:
                        output_error(
                            ctx,
                            f"Step {s.step_id} is in_progress — kill it first",
                            1,
                        )
                    s.status = StepStatus.pending
                    s.started_at = None
                    s.completed_at = None
                    reset_step_ids.append(s.step_id)

            # If the work item is failed or completed, reset to in_progress
            work_item = session.execute(
                select(WorkItem).where(
                    WorkItem.project_id == project_id,
                    WorkItem.id == item_id,
                )
            ).scalar_one_or_none()

            if work_item and work_item.status in (
                WorkItemStatus.failed,
                WorkItemStatus.completed,
            ):
                work_item.status = WorkItemStatus.in_progress
                work_item.completed_at = None

            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "project_id": project_id,
                    "item_id": item_id,
                    "from_step": step_id,
                    "reset_steps": reset_step_ids,
                }
            )
        )
    else:
        click.echo(f"Reset {item_id} from step {step_id}: {', '.join(reset_step_ids)} → pending")


# ---------------------------------------------------------------------------
# step-skip: mark a failed step as skipped
# ---------------------------------------------------------------------------


@click.command("step-skip")
@click.argument("item_id")
@click.option("--step", "step_id", required=True, help="Step ID (e.g., S01)")
@click.option("--reason", default=None, help="Why the step is being skipped")
@click.pass_context
def step_skip(ctx: click.Context, item_id: str, step_id: str, reason: str | None) -> None:
    """Skip a failed step (failed → skipped)."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            step = _find_step(session, project_id, item_id, step_id)
            if step is None:
                output_error(
                    ctx,
                    f"Step {step_id} not found for item {item_id} in project {project_id}",
                    1,
                )

            error = validate_step_skip_transition(step.status)
            if error:
                output_error(ctx, error, 1)

            step.status = StepStatus.skipped
            step.completed_at = datetime.now(UTC)

            # Store skip reason on the latest step_run if one exists
            if reason:
                last_run = session.execute(
                    select(StepRun)
                    .where(StepRun.step_id == step.id)
                    .order_by(StepRun.run_number.desc())
                    .limit(1)
                ).scalar_one_or_none()

                if last_run is not None:
                    last_run.error_message = f"Skipped: {reason}"

            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "project_id": project_id,
                    "item_id": item_id,
                    "step_id": step_id,
                    "status": "skipped",
                    "reason": reason,
                }
            )
        )
    else:
        msg = f"Skipped {item_id} step {step_id}"
        if reason:
            msg += f": {reason}"
        click.echo(msg)


# ---------------------------------------------------------------------------
# step-kill: terminate a running step's process
# ---------------------------------------------------------------------------


@click.command("step-kill")
@click.argument("item_id")
@click.option("--step", "step_id", required=True, help="Step ID (e.g., S01)")
@click.option("--reason", default="Manually killed via CLI", help="Kill reason")
@click.pass_context
def step_kill(ctx: click.Context, item_id: str, step_id: str, reason: str) -> None:
    """Kill a running step's process and mark it as failed."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]
    killed_pid: int | None = None

    try:
        with get_session() as session:
            step = _find_step(session, project_id, item_id, step_id)
            if step is None:
                output_error(
                    ctx,
                    f"Step {step_id} not found for item {item_id} in project {project_id}",
                    1,
                )

            error = validate_step_kill_transition(step.status)
            if error:
                output_error(ctx, error, 1)

            # Find the active run
            active_run = session.execute(
                select(StepRun)
                .where(
                    StepRun.step_id == step.id,
                    StepRun.status.in_([RunStatus.running, RunStatus.stalled]),
                )
                .order_by(StepRun.run_number.desc())
                .limit(1)
            ).scalar_one_or_none()

            if active_run is None:
                output_error(ctx, "No active run found for this step", 1)

            # Send SIGTERM to the process if PID exists
            if active_run.pid is not None:
                killed_pid = active_run.pid
                try:
                    os.kill(active_run.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass  # Already dead — still mark as killed
                except PermissionError:
                    output_error(
                        ctx,
                        f"Permission denied killing PID {active_run.pid}",
                        1,
                    )

            # Mark run as killed
            now = datetime.now(UTC)
            active_run.status = RunStatus.killed
            active_run.error_message = reason
            active_run.pid_alive = False
            active_run.completed_at = now
            if active_run.started_at:
                active_run.duration_secs = (now - active_run.started_at).total_seconds()

            # Mark step as failed
            step.status = StepStatus.failed
            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "project_id": project_id,
                    "item_id": item_id,
                    "step_id": step_id,
                    "status": "failed",
                    "killed_pid": killed_pid,
                    "reason": reason,
                }
            )
        )
    else:
        pid_info = f" (PID {killed_pid})" if killed_pid else ""
        click.echo(f"Killed {item_id} step {step_id}{pid_info}: {reason}")
