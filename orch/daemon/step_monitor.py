"""Step monitor — health checks for running step_runs.

Called every poll cycle for each project. Detects:
- Dead PIDs (crashed without reporting)
- Timeouts (exceeded configured limit)
- Stalls (PID alive but no heartbeat progress)
"""

from __future__ import annotations

import logging
import os
import signal
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from orch.db.models import DaemonEvent, RunStatus, StepRun, StepStatus, WorkflowStep

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.config import DaemonConfig
    from orch.daemon.project_registry import ProjectConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform timeout defaults (seconds)
# ---------------------------------------------------------------------------

PLATFORM_TIMEOUT_DEFAULTS: dict[str, int] = {
    "implementation": 2700,
    "code_review": 1800,
    "code_review_fix": 2700,
    "code_review_final": 2400,
    "code_review_fix_final": 2700,
    "quality_validation": 600,
    "qv_fix": 1800,
    "browser_verification": 900,
}
_FALLBACK_TIMEOUT = 1800


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def get_timeout(
    project_config: ProjectConfig,
    step_type: str,
    step_config: dict[str, Any] | None = None,
) -> int:
    """Resolve timeout (seconds) for a step type via the 3-level override chain.

    Priority (highest → lowest):
    1. Step-level override: ``step_config["timeout_secs"]``
    2. Project-level override: ``.iw-orch.json`` ``timeout_overrides[step_type]``
    3. Platform defaults (``PLATFORM_TIMEOUT_DEFAULTS``), fallback 1800s.
    """
    # 1. Step-level override
    if step_config and "timeout_secs" in step_config:
        return int(step_config["timeout_secs"])

    # 2. Project-level override
    project_overrides: dict[str, Any] = project_config.config.get("timeout_overrides", {})
    if step_type in project_overrides:
        return int(project_overrides[step_type])

    # 3. Platform defaults
    return PLATFORM_TIMEOUT_DEFAULTS.get(step_type, _FALLBACK_TIMEOUT)


def kill_process(pid: int) -> bool:
    """Send SIGTERM to ``pid``.

    Returns True if the signal was delivered, False if the process was already dead.
    """
    try:
        os.kill(pid, signal.SIGTERM)
        logger.info("Sent SIGTERM to PID %d", pid)
        return True
    except ProcessLookupError:
        logger.debug("PID %d already dead — SIGTERM not sent", pid)
        return False


def monitor_running_steps(
    db: Session,
    project_id: str,
    config: DaemonConfig,
) -> None:
    """Check all running step_runs for the given project.

    For each running StepRun:
    - PID dead (or None) → mark failed (step_crashed event).
    - PID alive + timeout exceeded → SIGTERM + mark timeout (step_timeout event).
    - PID alive + heartbeat stale → mark stalled (step_stalled event, not terminal).
    - PID alive + healthy → update pid_alive + last_heartbeat, no state change.
    """
    runs = (
        db.query(StepRun)
        .join(WorkflowStep, StepRun.step_id == WorkflowStep.id)
        .filter(
            WorkflowStep.project_id == project_id,
            StepRun.status == RunStatus.running,
        )
        .all()
    )

    for run in runs:
        _check_step_health(db, run, project_id, config)

    db.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_pid_alive(pid: int | None) -> bool:
    """Return True if the process is alive (kill -0)."""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _check_step_health(
    db: Session,
    run: StepRun,
    project_id: str,
    config: DaemonConfig,
) -> None:
    """Evaluate health of a single running StepRun and act on it."""
    now = datetime.now(UTC)
    alive = _is_pid_alive(run.pid)
    run.pid_alive = alive

    if not alive:
        _handle_crashed(db, run, project_id, now)
        return

    # PID is alive — snapshot old heartbeat before updating it
    old_heartbeat = run.last_heartbeat
    run.last_heartbeat = now

    # Check timeout (higher priority than stall)
    if run.started_at is not None and run.timeout_secs is not None:
        elapsed = (now - run.started_at).total_seconds()
        if elapsed > run.timeout_secs:
            _handle_timeout(db, run, project_id, now, elapsed)
            return

    # Check stall using the heartbeat from before this poll cycle
    if old_heartbeat is not None:
        heartbeat_age = (now - old_heartbeat).total_seconds()
        if heartbeat_age > config.stall_threshold:
            _handle_stall(db, run, project_id, config.stall_threshold)


def _handle_crashed(
    db: Session,
    run: StepRun,
    project_id: str,
    now: datetime,
) -> None:
    """Mark a StepRun as failed due to dead or missing PID."""
    msg = (
        "No PID recorded"
        if run.pid is None
        else "Process exited without reporting completion (PID dead)"
    )
    run.status = RunStatus.failed
    run.error_message = msg
    run.completed_at = now
    if run.started_at is not None:
        run.duration_secs = (now - run.started_at).total_seconds()
    capture_log_content(run)

    _update_parent_step(db, run.step_id, StepStatus.failed, now)
    _emit_event(db, project_id, "step_crashed", str(run.id), msg, {"pid": run.pid})
    logger.warning("step_run %d crashed: %s", run.id, msg)


def _handle_timeout(
    db: Session,
    run: StepRun,
    project_id: str,
    now: datetime,
    elapsed: float,
) -> None:
    """SIGTERM the process and mark a StepRun as timed out."""
    msg = f"Timeout after {elapsed:.0f}s (limit: {run.timeout_secs}s)"
    if run.pid is not None:
        kill_process(run.pid)

    run.status = RunStatus.timeout
    run.error_message = msg
    run.completed_at = now
    run.duration_secs = elapsed
    capture_log_content(run)

    _update_parent_step(db, run.step_id, StepStatus.failed, now)
    _emit_event(
        db,
        project_id,
        "step_timeout",
        str(run.id),
        msg,
        {"pid": run.pid, "elapsed_secs": elapsed, "timeout_secs": run.timeout_secs},
    )
    logger.warning("step_run %d timed out: %s", run.id, msg)


def _handle_stall(
    db: Session,
    run: StepRun,
    project_id: str,
    stall_threshold: int,
) -> None:
    """Mark a StepRun as stalled (PID alive but heartbeat is stale)."""
    msg = f"No progress for {stall_threshold}s"
    run.status = RunStatus.stalled
    run.error_message = msg

    _emit_event(db, project_id, "step_stalled", str(run.id), msg, {"pid": run.pid})
    logger.warning("step_run %d stalled: %s", run.id, msg)


def _update_parent_step(
    db: Session,
    step_id: int,
    new_status: StepStatus,
    now: datetime,
) -> None:
    """Update the parent WorkflowStep status.

    Only transitions from in_progress — if the step was already completed
    (e.g., agent called step-done before the PID exited), do not regress it.
    """
    step = db.get(WorkflowStep, step_id)
    if step is not None and step.status == StepStatus.in_progress:
        step.status = new_status
        if new_status in (StepStatus.completed, StepStatus.failed):
            step.completed_at = now


def _emit_event(
    db: Session,
    project_id: str,
    event_type: str,
    entity_id: str | None,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert a DaemonEvent row (caller is responsible for committing)."""
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=entity_id,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(event)
