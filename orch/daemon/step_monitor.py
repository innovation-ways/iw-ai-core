"""Step monitor — health checks for running step_runs.

Called every poll cycle for each project. Detects:
- Dead PIDs (crashed without reporting)
- Timeouts (exceeded configured limit)
- Stalls (PID alive but no heartbeat progress)
"""

from __future__ import annotations

import json
import logging
import os
import signal
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orch.db.models import DaemonEvent, RunStatus, StepRun, StepStatus, StepType, WorkflowStep
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
    "integration-tests": 1200,
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


def _has_agent_cmdline(pid: int | None) -> bool:
    """Return True if pid identifies a live agent process.

    Checks both the /proc/PID/cmdline CWD hint (for agents like opencode that
    change their working directory to the worktree root) and the /comm filename
    (for agents that rename via exec -a where the path won't appear in cmdline).
    Returns False for zombies or processes whose cmdline/comm does not match.
    """
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False

    # Check the cmdline CWD hint (line the agent changed into worktree root)
    try:
        with open(f"/proc/{pid}/cwd") as f:  # noqa: PTH123, SIM115, WPS515
            cwd = f.read().strip()
        if cwd.endswith(("/orch", "/ai-dev")) or "/worktrees/" in cwd:
            return True
    except OSError:
        pass

    # Check /proc/PID/cmdline for agent binary path
    try:
        with open(f"/proc/{pid}/cmdline") as f:  # noqa: PTH123, SIM115, WPS515
            cmdline = f.read()
        for candidate in ("opencode", "claude", "pi", "claude-code"):
            if candidate in cmdline:
                return True
    except OSError:
        pass

    # Check /proc/PID/comm for exec -a renamed processes
    try:
        with open(f"/proc/{pid}/comm") as f:  # noqa: PTH123, SIM115, WPS515
            comm = f.read().strip()
        if comm in ("opencode", "claude", "pi", "claude-code"):
            return True
    except OSError:
        pass

    return False


_REVIEW_STEP_TYPES = (StepType.code_review, StepType.code_review_final)


def _try_recover_completed_review_step(
    db: Session,
    run: StepRun,
    project_id: str,
    now: datetime,
) -> bool:
    """Return True if the run was successfully recovered from an on-disk report.

    Only applies to ``run.step_type in ('code_review', 'code_review_final')``.
    Looks for ``ai-dev/active/<work_item_id>/reports/<work_item_id>_<step_id>_*_report.md``
    with mtime > ``run.started_at``. Parses the JSON contract block. If verdict
    is recognised, persists the recovery via the same path ``iw step-done`` uses
    (i.e. mark the step ``completed`` with a per-agent verdict, OR ``needs_fix``
    when verdict='fail' and ``mandatory_fix_count > 0``). Records a DaemonEvent
    of type ``step_run_recovered_from_report``. Returns True on success, False
    if no report is found / the report is malformed / the step type is not a
    review type (caller falls through to ``_handle_crashed``).
    """
    # Resolve the project/worktree root so the glob is anchored at the project.
    worktree_root = None
    if run.worktree_path:
        worktree_root = run.worktree_path
    if worktree_root is None:
        return False

    # run.step_id is the integer FK to workflow_steps.id; report files are named
    # with the string step identifier (e.g. "S02"), so we must look up the step.
    # step_type lives on WorkflowStep, NOT on StepRun — read it from ws to avoid
    # AttributeError in production (I-00116 F4 fix).
    ws = db.get(WorkflowStep, run.step_id)
    if ws is None:
        return False
    step_str = ws.step_id
    work_item_id = ws.work_item_id

    # Guard: only code_review / code_review_final steps are recovered from reports.
    if ws.step_type not in _REVIEW_STEP_TYPES:
        return False

    paths_str = [
        str(p)
        for p in Path(worktree_root).glob(
            f"ai-dev/active/{work_item_id}/reports/{work_item_id}_{step_str}_*_report.md"
        )
    ]
    if not paths_str:
        logger.warning(
            "I-00116 run %s (work_item=%s step=%s): no report files matched glob pattern",
            run.id,
            work_item_id,
            step_str,
        )
        return False

    # Sort by mtime descending — use the most recent report.
    try:
        paths_str.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
    except OSError as exc:
        logger.warning(
            "I-00116 run %s (work_item=%s step=%s): OSError sorting report mtimes: %s",
            run.id,
            work_item_id,
            step_str,
            exc,
        )
        return False

    report_path = paths_str[0]
    started_ts = run.started_at.timestamp() if run.started_at else 0.0
    try:
        report_mtime = Path(report_path).stat().st_mtime
    except OSError as exc:
        logger.warning(
            "I-00116 run %s (work_item=%s step=%s): OSError reading mtime of %s: %s",
            run.id,
            work_item_id,
            step_str,
            report_path,
            exc,
        )
        return False
    if report_mtime <= started_ts:
        return False

    # Parse the JSON contract block from the markdown report.
    try:
        text = Path(report_path).read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning(
            "I-00116 run %s (work_item=%s step=%s): OSError reading report %s: %s",
            run.id,
            work_item_id,
            step_str,
            report_path,
            exc,
        )
        return False

    contract: dict[str, Any] | None = None
    in_block = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```json"):
            in_block = True
            contract_text = ""
            continue
        if in_block:
            if stripped == "```" or stripped.startswith("```"):
                if contract_text:
                    try:
                        contract = json.loads(contract_text)
                    except json.JSONDecodeError as exc:
                        logger.warning(
                            "I-00116 run %s (work_item=%s step=%s): "
                            "JSON parse error in report %s: %s",
                            run.id,
                            work_item_id,
                            step_str,
                            report_path,
                            exc,
                        )
                        return False
                break
            contract_text += line + "\n"

    if contract is None:
        logger.warning(
            "I-00116 run %s (work_item=%s step=%s): no JSON block found in report %s",
            run.id,
            work_item_id,
            step_str,
            report_path,
        )
        return False

    verdict = contract.get("verdict")
    if verdict not in ("pass", "fail"):
        logger.warning(
            "I-00116 run %s (work_item=%s step=%s): unrecognised verdict %r in report %s",
            run.id,
            work_item_id,
            step_str,
            verdict,
            report_path,
        )
        return False

    mandatory_fix_count = contract.get("mandatory_fix_count", 0)

    # Persist the recovery — same state transitions as `iw step-done`.
    run.status = RunStatus.completed if verdict == "pass" else RunStatus.failed
    run.error_message = None
    run.completed_at = now
    if run.started_at is not None:
        run.duration_secs = (now - run.started_at).total_seconds()

    # I-00116: also mark the parent step needs_fix when verdict=fail and
    # mandatory_fix_count > 0 (consistent with how fix_cycle.py interprets
    # a failed review verdict).
    parent_status = StepStatus.completed
    if verdict == "fail" and mandatory_fix_count > 0:
        parent_status = StepStatus.needs_fix

    _update_parent_step(db, run.step_id, parent_status, now)

    # Emit structured DaemonEvent (event_metadata, NOT metadata — SQLAlchemy).
    report_mtime_iso = datetime.fromtimestamp(report_mtime, UTC).isoformat()
    _emit_event(
        db,
        project_id,
        "step_run_recovered_from_report",
        work_item_id,
        entity_type="work_item",
        message=f"Recovered from on-disk report: verdict={verdict}",
        metadata={
            "work_item_id": work_item_id,
            "step_id": step_str,
            "step_run_id": run.id,
            "report_path": str(report_path),
            "report_mtime_iso": report_mtime_iso,
            "verdict": verdict,
            "mandatory_fix_count": mandatory_fix_count,
        },
    )
    logger.info(
        "I-00116 recovered run %s step=%s/%s from report=%s verdict=%s",
        run.id,
        work_item_id,
        step_str,
        report_path,
        verdict,
    )
    return True


def _probe_for_child(wrapper_pid: int | None) -> bool:
    """Check whether a live agent child exists for the given wrapper PID.


    Three-tier scan:
      1. Direct-children via /proc/PID/task/TID/children (kernel API)
      2. Full /proc scan for PPID=wrapper_pid
      3. Orphan fallback: scan /proc for PPID=1 and check cmdline for agent

    Returns True if any of the above finds a live agent child.
    """
    if wrapper_pid is None:
        return False

    # Tier 1: kernel-supplied children list
    try:
        for tid in os.listdir(f"/proc/{wrapper_pid}/task"):  # noqa: PTH102, PTH208, FIPS18
            children_path = f"/proc/{wrapper_pid}/task/{tid}/children"
            try:
                with open(children_path) as f:  # noqa: PTH123, SIM115, WPS515
                    children_str = f.read().strip()
                for child_pid_str in children_str.split():
                    child_pid = int(child_pid_str)
                    if _has_agent_cmdline(child_pid):
                        return True
            except OSError:
                continue
    except OSError:
        pass

    # Tier 2: full /proc scan for PPID = wrapper_pid
    try:
        for entry in os.listdir("/proc"):  # noqa: PTH208, FIPS18
            if not entry.isdigit():
                continue
            pid = int(entry)
            try:
                stat = open(f"/proc/{pid}/stat").read()  # noqa: PTH123, SIM115, WPS515
                # Fields: pid (0) cmd (1) state (2) ppid (3) ...
                parts = stat.split()
                if len(parts) >= 4 and int(parts[3]) == wrapper_pid and _has_agent_cmdline(pid):
                    return True
            except (OSError, ValueError):
                continue
    except OSError:
        pass

    # Tier 3: orphan fallback — PPID=1 scan
    try:
        for entry in os.listdir("/proc"):  # noqa: PTH208, FIPS18
            if not entry.isdigit():
                continue
            pid = int(entry)
            try:
                stat = open(f"/proc/{pid}/stat").read()  # noqa: PTH123, SIM115, WPS515
                parts = stat.split()
                if len(parts) >= 4 and int(parts[3]) == 1 and _has_agent_cmdline(pid):  # noqa: E501
                    return True
            except (OSError, ValueError):
                continue
    except OSError:
        pass

    return False


def _check_step_health(
    db: Session,
    run: StepRun,
    project_id: str,
    config: DaemonConfig,
    project_config: ProjectConfig | None = None,
) -> None:
    """Evaluate health of a single running StepRun and handle any abnormal state.

    Performs the following checks in order: PID liveness, child-process probe
    (for wrapper-shell exit), on-disk report recovery (code_review steps),
    timeout, 50%-timeout soft-warn, and stall/hard-stall detection.

    Args:
        db: Active database session — caller commits after all runs are checked.
        run: The StepRun in ``running`` status to evaluate.
        project_id: Project identifier for DaemonEvent routing.
        config: Daemon configuration providing the stall threshold.
        project_config: Optional project configuration for browser-env teardown.
    """
    now = datetime.now(UTC)
    alive = _is_pid_alive(run.pid)
    run.pid_alive = alive

    # CR-00065: resolve and persist the pi session file on the first poll cycle
    # that sees this run as alive (or every poll until it is found).
    if alive and run.session_file is None:
        _maybe_resolve_pi_session_file(db, run, now)

    # CR-00066: extract token counts from the pi session JSONL and update
    # context_tokens_last / context_tokens_peak for all alive pi runs that have
    # a resolved session file (peak never decreases; last may drop after compaction).
    if alive and run.session_file is not None:
        _update_token_counts(run)

    if not alive:
        # Belt-and-suspenders: if iw step-done already finalized this run,
        # never classify it as crashed. Fast-path this before the expensive
        # orphan scan.
        if getattr(run, "completed_at", None) is not None:
            return

        # I-00113: probe child processes before declaring crash.
        # The wrapper may have exited (its PID is dead) but the real agent child
        # is still alive and running. The orphan-fallback scan catches cases
        # where intermediate shell processes have also exited (PPID=1).
        if _probe_for_child(run.pid):
            run.pid_alive = True
            run.last_heartbeat = now
            # Update session file if this is the first poll where the child was found
            if run.session_file is None:
                _maybe_resolve_pi_session_file(db, run, now)
            if run.session_file is not None:
                _update_token_counts(run)
            return
        if getattr(run, "completed_at", None) is not None:
            return
        # I-00116: before marking crashed, check whether a well-formed verdict
        # report exists on disk for code_review steps. This closes the failure
        # mode where the agent exited cleanly but forgot to call `iw step-done`.
        if _try_recover_completed_review_step(db, run, project_id, now):
            return
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


# ---------------------------------------------------------------------------
# CR-00065: pi session file resolution
# ---------------------------------------------------------------------------

_PI_SESSIONS_DIR = Path.home() / ".pi" / "agent" / "sessions"


def _extract_latest_tokens(session_file: str) -> int | None:
    """Extract totalTokens from the most recent assistant message in a pi session JSONL.

    Iterates lines in reverse order (from the end) to find the most recent
    ``type == "message"`` entry where ``message.role == "assistant"`` and
    ``message.usage`` is present.  Returns ``message.usage.get("totalTokens")``
    as an int, or ``None`` if no qualifying entry is found.

    All filesystem/parse errors are swallowed and return ``None`` silently.
    """
    try:
        with open(session_file, encoding="utf-8") as fh:  # noqa: PTH123
            lines = fh.readlines()
    except OSError:
        return None

    for raw_line in reversed(lines):
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue

        if (
            obj.get("type") == "message"
            and isinstance(obj.get("message"), dict)
            and obj["message"].get("role") == "assistant"
            and "usage" in obj["message"]
        ):
            total = obj["message"]["usage"].get("totalTokens")
            if isinstance(total, int):
                return total

    return None


def _update_token_counts(run: StepRun) -> None:
    """Update context_tokens_last and context_tokens_peak from the pi session JSONL.

    Called every poll cycle for alive ``pi`` StepRuns with a resolved session_file.
    - ``context_tokens_last`` tracks the most recent token count (may drop after compaction).
    - ``context_tokens_peak`` is the all-time high-water mark and never decreases.

    Filesystem errors are swallowed — a corrupt session file never crashes the poll loop.
    """
    if run.cli_tool != "pi" or run.session_file is None:
        return

    try:
        latest = _extract_latest_tokens(run.session_file)
    except Exception:
        return

    if latest is None:
        return

    run.context_tokens_last = latest
    if run.context_tokens_peak is None or latest > run.context_tokens_peak:
        run.context_tokens_peak = latest


def _resolve_pi_session_file(run: StepRun) -> str | None:
    """Locate the most recently modified .jsonl file in the pi session dir for this worktree.

    Pi derives its session directory slug from the working directory by replacing
    each ``/`` with ``-``:
        /home/user/.../CR-00065  →  --home-user-...-CR-00065--

    The session directory is therefore:
        ~/.pi/agent/sessions/{slug}/

    We scan for ``.jsonl`` files in that directory whose mtime is greater than or
    equal to ``run.started_at`` (the step was started after the file was created
    or was being created at the time).  The most recently modified file is
    returned, or ``None`` if the directory does not exist or no qualifying file
    is found.

    All filesystem errors are swallowed and return ``None`` so that poll-cycle
    failures never crash the daemon health-check loop.
    """
    if run.cli_tool != "pi":
        return None
    if run.worktree_path is None:
        return None

    slug = f"--{run.worktree_path.lstrip('/').replace('/', '-')}--"
    session_dir = _PI_SESSIONS_DIR / slug

    try:
        if not session_dir.is_dir():
            return None
    except OSError:
        return None

    started_at = run.started_at
    best_path: str | None = None
    best_mtime = 0.0

    try:
        jsonl_files = session_dir.glob("*.jsonl")
    except OSError:
        return None

    for path in jsonl_files:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue

        if started_at is not None and mtime < started_at.timestamp():
            continue

        if mtime > best_mtime:
            best_mtime = mtime
            best_path = str(path)

    return best_path


def _maybe_resolve_pi_session_file(
    db: Session,  # noqa: ARG001 — kept for future DB writes; harmless no-op today
    run: StepRun,
    now: datetime,  # noqa: ARG001 — reserved for future use (e.g. event emission)
) -> None:
    """Attempt to resolve and persist the pi session file for a running StepRun.

    Called every poll cycle for any alive ``pi`` StepRun whose
    ``session_file`` column is still ``NULL``.  On success the path is
    written back to the DB row; the caller is responsible for committing.
    """
    try:
        session_file = _resolve_pi_session_file(run)
    except Exception:
        logger.warning(
            "step_run %d: _resolve_pi_session_file raised an exception (non-fatal)",
            run.id,
            exc_info=True,
        )
        return

    if session_file is not None:
        run.session_file = session_file
        logger.debug("step_run %d: resolved pi session file %s", run.id, session_file)
