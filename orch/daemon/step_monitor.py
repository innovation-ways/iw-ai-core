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
from orch.utils.log_capture import capture_log_content

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
    "browser_verification": 1800,
    "qv_browser_fix": 2700,
}

# CR-00024: per-gate defaults inserted between project-override and per-step-type
# bucket. Real workloads diverge wildly inside `quality_validation` (lint runs
# in 30s; integration tests routinely run 5–10 min). The legacy single bucket
# of 600s caused S14 of I-00041 to inherit too-tight a timeout.
QV_GATE_TIMEOUT_DEFAULTS: dict[str, int] = {
    "lint": 120,
    "format": 120,
    "typecheck": 240,
    "unit-tests": 300,
    "integration-tests": 900,
    "frontend-tests": 600,
    "browser": 1800,
}
_FALLBACK_TIMEOUT = 1800


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def get_timeout(
    project_config: ProjectConfig,
    step_type: str,
    step_config: dict[str, Any] | None = None,
    *,
    step: WorkflowStep | None = None,
) -> int:
    """Resolve timeout (seconds) for a step via the 4-level override chain.

    Priority (highest → lowest):
    1. Step-level override: ``step_config["timeout_secs"]``
    2. Project-level override: ``.iw-orch.json`` ``timeout_overrides[step_type]``
    3. **CR-00024** Per-gate default for QV steps with a known ``step.gate``.
    4. Platform defaults (``PLATFORM_TIMEOUT_DEFAULTS``), fallback 1800s.

    The ``step`` argument is keyword-only and optional so legacy call sites
    that don't have a ``WorkflowStep`` handy still work — they just skip
    the per-gate lookup and fall through to the per-type bucket.
    """
    # 1. Step-level override (manifest's `timeout` ingested at register time)
    if step_config and "timeout_secs" in step_config:
        return int(step_config["timeout_secs"])

    # 2. Project-level override
    project_overrides: dict[str, Any] = project_config.config.get("timeout_overrides", {})
    if step_type in project_overrides:
        return int(project_overrides[step_type])

    # 3. CR-00024: per-gate default. Only consulted when the step row carries
    # a non-NULL `gate` (i.e., it was registered after CR-00023). Legacy items
    # with NULL gate fall through to the per-type bucket below.
    if step is not None and step.gate is not None:
        gate_default = QV_GATE_TIMEOUT_DEFAULTS.get(step.gate)
        if gate_default is not None:
            return gate_default

    # 4. Platform defaults
    return PLATFORM_TIMEOUT_DEFAULTS.get(step_type, _FALLBACK_TIMEOUT)


def kill_process_group(pid: int) -> bool:
    """Send SIGTERM to the entire process group of ``pid``.

    Agents are launched with ``start_new_session=True`` (new session/pgid).
    Killing the process group ensures child processes (e.g. the inner agent
    spawned by ``script -qec``) also receive SIGTERM rather than only the
    shell wrapper that started them.

    Falls back to a single-PID kill if the process group lookup fails
    (e.g. the process already exited between the check and the kill).

    Returns True if a signal was delivered, False if the process was already
    dead or the caller has no permission to signal it.
    """
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGTERM)
        logger.info("Sent SIGTERM to process group PGID %d (PID %d)", pgid, pid)
        return True
    except (ProcessLookupError, PermissionError):
        # Process group gone or inaccessible — try single-PID kill as fallback.
        pass
    try:
        os.kill(pid, signal.SIGTERM)
        logger.info("Sent SIGTERM to PID %d (fallback from process-group kill)", pid)
        return True
    except (ProcessLookupError, PermissionError):
        logger.debug("PID %d already dead — SIGTERM not sent", pid)
        return False


def kill_process(pid: int) -> bool:
    """Send SIGTERM to the process group of ``pid``.

    Kept for back-compatibility; delegates to ``kill_process_group``.
    """
    return kill_process_group(pid)


def monitor_running_steps(
    db: Session,
    project_id: str,
    config: DaemonConfig,
    project_config: ProjectConfig | None = None,
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
        _check_step_health(db, run, project_id, config, project_config)

    db.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_pid_alive(pid: int | None) -> bool:
    """Return True if the process is alive and not a zombie.

    Uses /proc/{pid}/stat on Linux to detect zombie state (state 'Z').
    Zombie processes pass kill -0 but are effectively dead — their parent
    has not yet called wait(), so the process table entry lingers.
    """
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    # kill -0 succeeded — but the process may be a zombie
    try:
        stat = open(f"/proc/{pid}/stat").read()  # noqa: PTH123, SIM115, WPS515
        # Field 3 in /proc/pid/stat is the process state (Z = zombie)
        state = stat.split("(", 1)[-1].rsplit(")", 1)[-1].split()[0]
        return state != "Z"
    except OSError:
        # /proc not available (non-Linux) — assume alive
        return True


def _check_step_health(
    db: Session,
    run: StepRun,
    project_id: str,
    config: DaemonConfig,
    project_config: ProjectConfig | None = None,
) -> None:
    """Evaluate health of a single running StepRun and act on it."""
    now = datetime.now(UTC)
    alive = _is_pid_alive(run.pid)
    run.pid_alive = alive

    if not alive:
        _handle_crashed(db, run, project_id, now, project_config)
        return

    # PID is alive — snapshot old heartbeat before updating it
    old_heartbeat = run.last_heartbeat
    run.last_heartbeat = now

    # Check timeout (higher priority than stall and 50%-warn)
    if run.started_at is not None and run.timeout_secs is not None:
        elapsed = (now - run.started_at).total_seconds()
        if elapsed > run.timeout_secs:
            _handle_timeout(db, run, project_id, now, elapsed, project_config)
            return

        # CR-00024: one-time 50%-of-timeout soft-warn. Only fires when we've
        # not yet emitted it for this run (warned_50pct_at IS NULL) AND the
        # timeout branch above did NOT fire (the `return` there ensures AC5).
        if elapsed > run.timeout_secs * 0.5 and run.warned_50pct_at is None:
            _handle_warn_50pct(db, run, project_id, now, elapsed)

    # Check stall using the heartbeat from before this poll cycle.
    # Hard stall (>= 2x threshold): kill the process and fail the step.
    # Soft stall (>= 1x threshold): emit event but keep running (existing behavior).
    if old_heartbeat is not None:
        heartbeat_age = (now - old_heartbeat).total_seconds()
        if heartbeat_age > config.stall_threshold * 2:
            _handle_hard_stall(db, run, project_id, now, heartbeat_age, project_config)
            return
        if heartbeat_age > config.stall_threshold:
            _handle_stall(db, run, project_id, config.stall_threshold)


def _handle_crashed(
    db: Session,
    run: StepRun,
    project_id: str,
    now: datetime,
    project_config: ProjectConfig | None = None,
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

    # Tear down browser env if applicable (before emitting event)
    _maybe_teardown_browser_env(db, run, project_id, project_config)

    # Look up work_item_id for correct entity routing
    step = db.get(WorkflowStep, run.step_id)
    work_item_id = step.work_item_id if step else None

    _emit_event(
        db,
        project_id,
        "step_crashed",
        work_item_id,
        message=msg,
        entity_type="work_item",
        metadata={"pid": run.pid},
    )
    logger.warning("step_run %d crashed: %s", run.id, msg)


def _handle_timeout(
    db: Session,
    run: StepRun,
    project_id: str,
    now: datetime,
    elapsed: float,
    project_config: ProjectConfig | None = None,
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

    # Tear down browser env if applicable (before emitting event)
    _maybe_teardown_browser_env(db, run, project_id, project_config)

    # Look up work_item_id for correct entity routing
    step = db.get(WorkflowStep, run.step_id)
    work_item_id = step.work_item_id if step else None

    _emit_event(
        db,
        project_id,
        "step_timeout",
        work_item_id,
        message=msg,
        entity_type="work_item",
        metadata={"pid": run.pid, "elapsed_secs": elapsed, "timeout_secs": run.timeout_secs},
    )
    logger.warning("step_run %d timed out: %s", run.id, msg)


def _maybe_teardown_browser_env(
    db: Session,
    run: StepRun,
    project_id: str,
    project_config: ProjectConfig | None,
) -> None:
    """If the step is a browser_verification step, run the env_down hook.

    Looks up the parent WorkflowStep to check its type.  Never raises —
    any error is logged at WARNING level (teardown is best-effort).
    """
    if project_config is None:
        return

    try:
        from orch.daemon import browser_env  # noqa: PLC0415

        step = db.get(WorkflowStep, run.step_id)
        if step is None:
            return
        if not browser_env.is_browser_verification_step(step.step_type):
            return

        worktree_path = run.worktree_path or ""
        bv_env = browser_env.resolve_browser_env(
            project_config,
            project_id,
            step.work_item_id,
            worktree_path=worktree_path,
        )
        if bv_env is None:
            return

        browser_env.run_env_down_hook(
            project_config,
            worktree_path,
            bv_env,
            step.work_item_id,
            step.step_id,
        )
    except Exception:
        logger.warning(
            "step_run %d: browser env teardown raised an exception (non-fatal)",
            run.id,
            exc_info=True,
        )


def _handle_warn_50pct(
    db: Session,
    run: StepRun,
    project_id: str,
    now: datetime,
    elapsed: float,
) -> None:
    """CR-00024: one-time soft-warn when a running step crosses 50% of its timeout.

    Stamps ``run.warned_50pct_at`` to suppress duplicate warns across poll
    cycles and emits a non-terminal ``step_warning_50pct`` DaemonEvent. The
    StepRun status stays ``running`` — this is purely an observability signal.
    """
    run.warned_50pct_at = now
    timeout = run.timeout_secs or 0
    percent = int((elapsed / timeout) * 100) if timeout > 0 else 50
    msg = f"Step is past 50% of its timeout budget ({elapsed:.0f}s of {timeout}s, ~{percent}%)"

    step = db.get(WorkflowStep, run.step_id)
    work_item_id = step.work_item_id if step else None

    _emit_event(
        db,
        project_id,
        "step_warning_50pct",
        work_item_id,
        message=msg,
        entity_type="work_item",
        metadata={
            "pid": run.pid,
            "elapsed_secs": elapsed,
            "timeout_secs": timeout,
            "percent": percent,
        },
    )
    logger.info("step_run %d past 50%% of timeout: %s", run.id, msg)


def _handle_stall(
    db: Session,
    run: StepRun,
    project_id: str,
    stall_threshold: int,
) -> None:
    """Mark a StepRun as stalled (PID alive but heartbeat is stale).

    This is a soft stall (heartbeat_age between 1x and 2x stall_threshold).
    The process is not killed — only an event is emitted to surface the
    stall in the dashboard. The step remains in_progress.
    """
    msg = f"No progress for {stall_threshold}s"
    run.status = RunStatus.stalled
    run.error_message = msg

    # Look up work_item_id for correct entity routing
    step = db.get(WorkflowStep, run.step_id)
    work_item_id = step.work_item_id if step else None

    _emit_event(
        db,
        project_id,
        "step_stalled",
        work_item_id,
        message=msg,
        entity_type="work_item",
        metadata={"pid": run.pid},
    )
    logger.warning("step_run %d stalled: %s", run.id, msg)


def _handle_hard_stall(
    db: Session,
    run: StepRun,
    project_id: str,
    now: datetime,
    heartbeat_age: float,
    project_config: ProjectConfig | None = None,
) -> None:
    """Kill and fail a StepRun whose heartbeat has exceeded 2x the stall threshold.

    This is a "hard stall" — the process is unresponsive for so long that
    waiting further is counterproductive. We SIGTERM the process group (to
    catch child processes spawned by ``script -qec``), mark the run as failed,
    transition the parent step to failed, and emit a ``step_stall_killed`` event
    so the failure pathway (fix-cycle or retry logic) can take over immediately.
    """
    msg = f"Killed after stall (heartbeat exceeded {heartbeat_age:.0f}s)"
    if run.pid is not None:
        kill_process_group(run.pid)

    run.status = RunStatus.failed
    run.error_message = msg
    run.completed_at = now
    if run.started_at is not None:
        run.duration_secs = (now - run.started_at).total_seconds()
    capture_log_content(run)

    # Look up work_item_id for correct entity routing
    step = db.get(WorkflowStep, run.step_id)
    work_item_id = step.work_item_id if step else None

    _update_parent_step(db, run.step_id, StepStatus.failed, now)

    # Tear down browser env if applicable (before emitting event)
    _maybe_teardown_browser_env(db, run, project_id, project_config)

    _emit_event(
        db,
        project_id,
        "step_stall_killed",
        work_item_id,
        message=msg,
        entity_type="work_item",
        metadata={"pid": run.pid, "heartbeat_age_secs": heartbeat_age},
    )
    logger.warning("step_run %d hard-stalled and killed: %s", run.id, msg)


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
    entity_type: str | None = None,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert a DaemonEvent row (caller is responsible for committing)."""
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=entity_id,
        entity_type=entity_type,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(event)
