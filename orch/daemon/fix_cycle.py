"""Fix cycle management — automatic code review fix loops.

When a code_review or code_review_final step fails (agent found mandatory
findings), the daemon creates a FixCycle, launches a fix agent, and after
completion resets the review step to pending so it re-runs automatically.
Loops up to fix_cycle_max (default 5) times before giving up.
"""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from orch.db.models import (
    DaemonEvent,
    FixCycle,
    FixStatus,
    FixTrigger,
    QvBaseline,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

    from orch.config import DaemonConfig
    from orch.daemon.project_registry import ProjectConfig
    from orch.daemon.qv_baseline import Fingerprint

logger = logging.getLogger(__name__)

# Step types that can trigger fix cycles.
# browser_verification is fixable because V1..V(n) failures are real code
# defects caught by E2E checks, not transient environment issues — plain
# retries against unchanged code just re-fail three times and give up.
_FIXABLE_STEP_TYPES = frozenset(
    {
        StepType.code_review,
        StepType.code_review_final,
        StepType.quality_validation,
        StepType.browser_verification,
    }
)

# Step types that get plain retries (no LLM fix agent — just reset to pending).
# implementation: PID-dead / silent-exit failures get up to 2 retries, but only
# when the agent wrote no report (report_file and report_content both None).
# A present report means the agent reached end-of-step and deliberately failed;
# retrying against unchanged code would just re-fail.
_RETRYABLE_STEP_TYPES: frozenset[StepType] = frozenset({StepType.implementation})
_DEFAULT_BROWSER_VERIFY_MAX_RETRIES = 3
_DEFAULT_IMPLEMENTATION_MAX_RETRIES = 2

_TRIGGER_MAP: dict[StepType, FixTrigger] = {
    StepType.code_review: FixTrigger.code_review,
    StepType.code_review_final: FixTrigger.code_review_final,
    StepType.quality_validation: FixTrigger.quality_validation,
    StepType.browser_verification: FixTrigger.browser_verification,
}

_FIX_TIMEOUT_MAP: dict[StepType, str] = {
    StepType.code_review: "code_review_fix",
    StepType.code_review_final: "code_review_fix_final",
    StepType.quality_validation: "qv_fix",
    StepType.browser_verification: "qv_browser_fix",
}

_DEFAULT_FIX_CYCLE_MAX = 5
_MAX_FIX_SUMMARY_LEN = 20000
# Browser fix cycles rebuild the full E2E docker-compose stack on every
# re-run, which is expensive; cap them separately from the generic limit.
# Bumped to 3 from 2 after 4/6 recent browser_verification completions
# (CR-00019, F-00058, F-00056, F-00055) used both cycles — two stuck items
# (I-00038 S11, F-00060 S14) ran out on the first wrong-hypothesis step and
# never recovered. Three cycles gives agents room for one bad guess.
_DEFAULT_BROWSER_FIX_CYCLE_MAX = 3


# ---------------------------------------------------------------------------
# Internal: configured cycle limits
# ---------------------------------------------------------------------------


def _max_cycles_for(step_type: StepType, project_config: ProjectConfig) -> int:
    """Resolve max fix cycles for a step type (browser has a stricter default)."""
    if step_type is StepType.browser_verification:
        return int(
            project_config.config.get("browser_fix_cycle_max", _DEFAULT_BROWSER_FIX_CYCLE_MAX)
        )
    return int(project_config.config.get("fix_cycle_max", _DEFAULT_FIX_CYCLE_MAX))


# ---------------------------------------------------------------------------
# Public API (called from batch_manager)
# ---------------------------------------------------------------------------


_ENV_DATA_MISSING_PREFIX = "ENV_DATA_MISSING:"


def _latest_failure_reason(db: Session, step: WorkflowStep) -> str | None:
    """Return the error_message of the latest failed StepRun, or None."""
    latest = (
        db.query(StepRun)
        .filter(
            StepRun.step_id == step.id,
            StepRun.status.in_([RunStatus.failed, RunStatus.timeout]),
        )
        .order_by(StepRun.run_number.desc())
        .first()
    )
    if latest is None:
        return None
    return latest.error_message


def should_attempt_fix(
    db: Session,
    step: WorkflowStep,
    project_config: ProjectConfig,
) -> bool:
    """Return True if this failed step is a review that can be auto-fixed.

    Note: historically this function skipped the fix cycle entirely when a
    browser_verification failure started with ``ENV_DATA_MISSING:``. That
    guard was a footgun — every one of the real defects (wrong-DB insert,
    stub shape drift, swallowed exceptions, Jobs-page 500) the qv-browser
    agent mis-classified as "environmental" would have been fixable by a
    subsequent fix cycle, but the skip prevented it. The fix cycle now
    always runs within the max-cycles budget; the fix prompt tells the
    agent how to judge whether an earlier ENV_DATA_MISSING claim is real
    (write a fixture) or hiding a code defect (fix the defect).
    """
    if step.step_type not in _FIXABLE_STEP_TYPES:
        return False

    max_cycles = _max_cycles_for(step.step_type, project_config)
    existing = db.query(FixCycle).filter(FixCycle.step_id == step.id).count()

    if existing >= max_cycles:
        logger.warning(
            "Max fix cycles (%d) exhausted for step %d (%s/%s)",
            max_cycles,
            step.id,
            step.work_item_id,
            step.step_id,
        )
        return False

    return True


def should_retry_step(
    db: Session,
    step: WorkflowStep,
    project_config: ProjectConfig,
) -> bool:
    """Return True if this failed step should be retried (reset to pending) without a fix cycle.

    implementation steps are retried only when the agent exited without writing a report
    (PID-dead / silent exit). A present report means the agent deliberately stopped —
    retrying against unchanged code would just re-fail.
    """
    if step.step_type not in _RETRYABLE_STEP_TYPES:
        return False

    if step.step_type is StepType.implementation:
        if step.report_file is not None or step.report_content is not None:
            return False
        max_retries = int(
            project_config.config.get(
                "implementation_max_retries", _DEFAULT_IMPLEMENTATION_MAX_RETRIES
            )
        )
    else:
        max_retries = int(
            project_config.config.get(
                "browser_verify_max_retries", _DEFAULT_BROWSER_VERIFY_MAX_RETRIES
            )
        )

    run_count = db.query(StepRun).filter(StepRun.step_id == step.id).count()

    if run_count >= max_retries:
        logger.warning(
            "Max retries (%d) exhausted for step %d (%s/%s)",
            max_retries,
            step.id,
            step.work_item_id,
            step.step_id,
        )
        return False

    return True


def retry_step(
    db: Session,
    step: WorkflowStep,
    project_id: str,
) -> None:
    """Reset a retryable failed step back to pending so the daemon re-launches it."""
    run_count = db.query(StepRun).filter(StepRun.step_id == step.id).count()

    step.status = StepStatus.pending
    step.started_at = None
    step.completed_at = None

    _emit_event(
        db,
        project_id,
        "step_retry_scheduled",
        step.work_item_id,
        "work_item",
        f"Step {step.step_id} reset to pending for retry (attempt {run_count + 1})",
        {"step_id": step.step_id, "attempt": run_count + 1},
    )
    db.commit()

    logger.info(
        "[%s] Step %s/%s reset to pending for retry (attempt %d)",
        project_id,
        step.work_item_id,
        step.step_id,
        run_count + 1,
    )


def attempt_fix_cycle(
    db: Session,
    step: WorkflowStep,
    project_id: str,
    project_config: ProjectConfig,
    config: DaemonConfig,
    worktree_info: dict[str, Any],
) -> None:
    """Create a fix cycle, generate a fix prompt, and launch the fix agent."""
    worktree_path = worktree_info.get("path", "")
    if not worktree_path:
        logger.error(
            "No worktree path for %s/%s — cannot start fix cycle", project_id, step.step_id
        )
        return

    max_cycles = _max_cycles_for(step.step_type, project_config)
    existing_count = db.query(FixCycle).filter(FixCycle.step_id == step.id).count()
    cycle_number = existing_count + 1
    trigger = _TRIGGER_MAP[step.step_type]

    # --- Steps 1 & 2: findings extraction + prompt generation ---
    # These steps can raise (missing file, disk error, etc.). If they fail
    # we must still persist a FixCycle row with status=failed so that
    # should_attempt_fix() counts it toward max_cycles and prevents an
    # infinite re-launch loop (the daemon would otherwise see status=failed
    # with 0 FixCycle rows and keep calling attempt_fix_cycle forever).
    try:
        # Get the review findings from the latest failed StepRun
        findings = _get_review_findings(db, step, worktree_path, config)

        # Grab the latest StepRun's --reason so the fix prompt can call out
        # mis-classified ENV_DATA_MISSING / ENVIRONMENT failures.
        prior_reason = _latest_failure_reason(db, step)

        # Generate fix prompt
        prompt_path = _generate_fix_prompt(
            step,
            worktree_path,
            cycle_number,
            findings,
            max_cycles,
            prior_failure_reason=prior_reason,
        )
    except Exception as exc:
        # Record a failed FixCycle so the next poll's should_attempt_fix
        # increments toward max_cycles even when prompt generation can't complete.
        now = datetime.now(UTC)
        failed_cycle = FixCycle(
            step_id=step.id,
            cycle_number=cycle_number,
            trigger_type=trigger,
            trigger_report=step.report_file,
            fix_prompt=None,
            status=FixStatus.failed,
            started_at=now,
            completed_at=now,
            fix_metadata={
                "error": "prompt_generation_failed",
                "exception": str(exc),
            },
        )
        db.add(failed_cycle)
        db.commit()
        _emit_event(
            db,
            project_id,
            "fix_cycle_failed",
            step.work_item_id,
            "work_item",
            f"Fix cycle {cycle_number} prompt generation failed: {exc}",
            {"reason": "prompt_generation_failed", "cycle_number": cycle_number},
        )
        db.commit()
        logger.error(
            "[%s] Fix cycle %d prompt generation failed for %s/%s: %s",
            project_id,
            cycle_number,
            step.work_item_id,
            step.step_id,
            exc,
            exc_info=True,
        )
        # step.status remains failed — do not transition to needs_fix
        return

    # --- Steps 3+: persist FixCycle and launch agent ---
    # Transition step: failed → needs_fix
    step.status = StepStatus.needs_fix
    step.started_at = None
    step.completed_at = None

    # Create FixCycle record
    fix_cycle = FixCycle(
        step_id=step.id,
        cycle_number=cycle_number,
        trigger_type=trigger,
        trigger_report=step.report_file,
        fix_prompt=str(prompt_path) if prompt_path else None,
        status=FixStatus.pending,
    )
    db.add(fix_cycle)
    db.flush()  # Get fix_cycle.id

    # Launch fix agent
    pid, log_file, timeout = _launch_fix_agent(
        step,
        worktree_path,
        prompt_path,
        project_config,
        config,
        cycle_number,
    )

    now = datetime.now(UTC)
    fix_cycle.status = FixStatus.in_progress
    fix_cycle.started_at = now
    fix_cycle.fix_metadata = {
        "pid": pid,
        "log_file": str(log_file),
        "timeout_secs": timeout,
        "worktree_path": worktree_path,
    }

    db.commit()

    _emit_event(
        db,
        project_id,
        "fix_cycle_started",
        step.work_item_id,
        "work_item",
        f"Fix cycle {cycle_number}/{max_cycles} for {step.step_id} (PID {pid})",
        {
            "step_id": step.step_id,
            "cycle_number": cycle_number,
            "max_cycles": max_cycles,
            "pid": pid,
        },
    )
    logger.info(
        "[%s] Fix cycle %d/%d started for %s/%s (PID %d)",
        project_id,
        cycle_number,
        max_cycles,
        step.work_item_id,
        step.step_id,
        pid,
    )


def check_active_fix_cycles(
    db: Session,
    project_id: str,
    project_config: ProjectConfig,  # noqa: ARG001
    config: DaemonConfig,  # noqa: ARG001
) -> None:
    """Monitor all in-progress fix cycles: detect PID death or timeout."""
    cycles = (
        db.query(FixCycle)
        .join(WorkflowStep, FixCycle.step_id == WorkflowStep.id)
        .filter(
            WorkflowStep.project_id == project_id,
            FixCycle.status == FixStatus.in_progress,
        )
        .all()
    )

    for cycle in cycles:
        _check_fix_cycle_health(db, cycle, project_id)

    db.commit()


# ---------------------------------------------------------------------------
# Internal: health check for a single fix cycle
# ---------------------------------------------------------------------------


def _check_fix_cycle_health(
    db: Session,
    cycle: FixCycle,
    project_id: str,
) -> None:
    """Check if the fix agent process is still alive, timed out, or finished."""
    meta = cycle.fix_metadata or {}
    pid = meta.get("pid")
    timeout_secs = meta.get("timeout_secs", 2700)

    alive = _is_pid_alive(pid)
    now = datetime.now(UTC)

    if alive and cycle.started_at is not None:
        elapsed = (now - cycle.started_at).total_seconds()
        if elapsed > timeout_secs:
            # Kill the process and mark as failed
            _kill_pid(pid)
            _fail_fix_cycle(
                db,
                cycle,
                project_id,
                now,
                f"Fix agent timed out after {elapsed:.0f}s (limit: {timeout_secs}s)",
            )
            return
        # Still running — nothing to do
        return

    if alive:
        return  # Still running, no timeout info

    # PID is dead — fix agent finished (or crashed)
    _complete_fix_cycle(db, cycle, project_id, now)


def _complete_fix_cycle(
    db: Session,
    cycle: FixCycle,
    project_id: str,
    now: datetime,
) -> None:
    """Mark fix cycle as completed and reset the review step to pending."""
    cycle.status = FixStatus.completed
    cycle.completed_at = now

    step = db.get(WorkflowStep, cycle.step_id)
    if step is not None and step.project_id != project_id:
        logger.error(
            "Step %d belongs to project %s, expected %s",
            cycle.step_id,
            step.project_id,
            project_id,
        )
        return
    if step is not None and step.status == StepStatus.needs_fix:
        step.status = StepStatus.pending
        step.started_at = None
        step.completed_at = None

    _emit_event(
        db,
        project_id,
        "fix_cycle_completed",
        step.work_item_id if step else None,
        "work_item",
        f"Fix cycle {cycle.cycle_number} completed — re-running review",
        {"cycle_id": cycle.id, "cycle_number": cycle.cycle_number},
    )
    logger.info(
        "[%s] Fix cycle %d completed for step %d — review will re-run",
        project_id,
        cycle.cycle_number,
        cycle.step_id,
    )


def _fail_fix_cycle(
    db: Session,
    cycle: FixCycle,
    project_id: str,
    now: datetime,
    reason: str,
) -> None:
    """Mark fix cycle as failed and transition step back to failed."""
    cycle.status = FixStatus.failed
    cycle.completed_at = now

    step = db.get(WorkflowStep, cycle.step_id)
    if step is not None and step.project_id != project_id:
        logger.error(
            "Step %d belongs to project %s, expected %s",
            cycle.step_id,
            step.project_id,
            project_id,
        )
        return
    if step is not None and step.status == StepStatus.needs_fix:
        step.status = StepStatus.failed

    _emit_event(
        db,
        project_id,
        "fix_cycle_failed",
        step.work_item_id if step else None,
        "work_item",
        f"Fix cycle {cycle.cycle_number} failed: {reason}",
        {"cycle_id": cycle.id, "cycle_number": cycle.cycle_number, "reason": reason},
    )
    logger.warning(
        "[%s] Fix cycle %d failed for step %d: %s",
        project_id,
        cycle.cycle_number,
        cycle.step_id,
        reason,
    )


# ---------------------------------------------------------------------------
# Internal: findings extraction
# ---------------------------------------------------------------------------


def _get_review_findings(
    db: Session, step: WorkflowStep, worktree_path: str, config: DaemonConfig
) -> str:
    """Extract findings from the report file, StepRun error_message, or log content."""
    # For QV steps, prefer the step_run error and log content (command output)
    if step.step_type == StepType.quality_validation:
        return _get_qv_findings(db, step, worktree_path, config)

    # Browser verification reports have structured V1..V(n) tables + a root cause
    # section with file:line refs; the fix agent needs all of it, not just the
    # extracted severity blocks.
    if step.step_type == StepType.browser_verification:
        return _get_browser_findings(db, step, worktree_path)

    # Try report file first (structured content)
    if step.report_file:
        report_path = Path(worktree_path) / step.report_file
        if report_path.exists():
            content = report_path.read_text()
            findings = _extract_mandatory_findings(content)
            if findings:
                return findings

    # Try report_content stored in DB
    if step.report_content:
        findings = _extract_mandatory_findings(step.report_content)
        if findings:
            return findings

    # Fall back to the latest failed StepRun error_message
    latest_run = db.execute(
        select(StepRun)
        .where(
            StepRun.step_id == step.id,
            StepRun.status.in_([RunStatus.failed, RunStatus.timeout]),
        )
        .order_by(StepRun.run_number.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest_run and latest_run.error_message:
        return latest_run.error_message

    return "No findings available — review the code for issues flagged by the previous review."


def _get_browser_findings(db: Session, step: WorkflowStep, worktree_path: str) -> str:
    """Return the full browser_verification report (V table + root cause + refs).

    Browser reports are short and highly structured — we pass the whole thing so
    the fix agent sees failed Vs, expected vs. actual, screenshot paths, and any
    file:line references the qv-browser agent logged.
    """
    # Prefer the report file on disk
    if step.report_file:
        report_path = Path(worktree_path) / step.report_file
        if report_path.exists():
            content = report_path.read_text()
            return _truncate(content, 8000)

    # Fall back to DB-stored report content
    if step.report_content:
        return _truncate(step.report_content, 8000)

    # Last resort: latest failed StepRun's error_message
    latest_run = db.execute(
        select(StepRun)
        .where(
            StepRun.step_id == step.id,
            StepRun.status.in_([RunStatus.failed, RunStatus.timeout]),
        )
        .order_by(StepRun.run_number.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest_run and latest_run.error_message:
        return latest_run.error_message

    return (
        "No browser report available — inspect the latest qv-browser run log "
        "and infer the defect from the V(n) FAILED messages."
    )


def _truncate(content: str, limit: int) -> str:
    if len(content) <= limit:
        return content
    return content[:limit] + "\n\n...(report truncated for prompt length)..."


def _get_qv_findings(
    db: Session, step: WorkflowStep, worktree_path: str, config: DaemonConfig
) -> str:
    """Extract quality validation findings, applying baseline subtraction when enabled."""
    if not config.baseline_qv_enabled:
        return _qv_findings_legacy(db, step, worktree_path)

    gate_name, command = _get_gate_name_and_command(step, worktree_path)
    if not gate_name or not command:
        return _qv_findings_legacy(db, step, worktree_path)

    from orch.daemon.qv_baseline import (  # noqa: PLC0415
        GATE_PARSERS,
        fingerprint_from_jsonable,
        fingerprint_to_jsonable,
        subtract,
    )

    parser = GATE_PARSERS.get(gate_name)
    if parser is None:
        return _qv_findings_legacy(db, step, worktree_path)

    current_base_sha = _resolve_worktree_base_sha(worktree_path)
    if not current_base_sha:
        return _qv_findings_legacy(db, step, worktree_path)

    baseline_row = db.execute(
        select(QvBaseline).where(
            QvBaseline.step_id == step.id,
            QvBaseline.gate_name == gate_name,
        )
    ).scalar_one_or_none()

    if baseline_row is None:
        return _qv_findings_legacy(db, step, worktree_path)

    baseline_fp = fingerprint_from_jsonable(baseline_row.fingerprint)

    if baseline_row.base_sha != current_base_sha:
        logger.info(
            "[F-00061] Rebase invalidation for %s/%s: stored SHA %s != current %s",
            step.work_item_id,
            step.step_id,
            baseline_row.base_sha,
            current_base_sha,
        )
        db.delete(baseline_row)
        db.flush()
        new_fp = _recompute_baseline_for_gate(step, worktree_path, gate_name, command, parser)
        if new_fp is None:
            return _qv_findings_legacy(db, step, worktree_path)
        baseline_fp = new_fp
        now = datetime.now(UTC)
        baseline_row = QvBaseline(
            step_id=step.id,
            gate_name=gate_name,
            base_sha=current_base_sha,
            fingerprint=fingerprint_to_jsonable(baseline_fp),
            computed_at=now,
        )
        db.add(baseline_row)
        db.commit()

    latest_run = db.execute(
        select(StepRun)
        .where(
            StepRun.step_id == step.id,
            StepRun.status.in_([RunStatus.failed, RunStatus.timeout]),
        )
        .order_by(StepRun.run_number.desc())
        .limit(1)
    ).scalar_one_or_none()

    if not latest_run:
        return _qv_findings_legacy(db, step, worktree_path)

    current_output = ""
    if latest_run.log_content:
        current_output = latest_run.log_content
    elif latest_run.log_file:
        log_path = Path(latest_run.log_file)
        if log_path.exists():
            current_output = log_path.read_text()

    if not current_output:
        if latest_run.error_message:
            return f"**Error**: {latest_run.error_message}"
        return _qv_findings_legacy(db, step, worktree_path)

    current_fp = parser(current_output)
    delta = subtract(current_fp, baseline_fp)

    if not delta.failures and not delta.unparseable:
        logger.info(
            "[F-00061] Suppressed %d pre-existing failures for %s/%s",
            len(baseline_fp.failures),
            step.work_item_id,
            step.step_id,
        )
        return ""

    return _format_qv_findings_from_delta(delta, latest_run)


def _get_gate_name_and_command(
    step: WorkflowStep, worktree_path: str
) -> tuple[str | None, str | None]:
    """Resolve (gate_name, command) for a QV step.

    DB-first per CR-00023: returns the WorkflowStep row's columns when
    populated. Falls back to the on-disk manifest for legacy items
    registered before those columns existed.
    """
    if step.command:
        return (step.gate or step.step_id), step.command

    import json

    manifest_path = (
        Path(worktree_path) / "ai-dev" / "active" / step.work_item_id / "workflow-manifest.json"
    )
    if not manifest_path.exists():
        return None, None
    try:
        manifest = json.loads(manifest_path.read_text())
        for s in manifest.get("steps", []):
            if s.get("step") == step.step_id:
                gate = s.get("gate", step.step_id)
                command = s.get("command")
                return gate, command
    except Exception:  # noqa: S110
        pass
    return None, None


def _resolve_worktree_base_sha(worktree_path: str) -> str | None:
    """Resolve the worktree's base SHA via git merge-base HEAD main."""
    try:
        result = subprocess.run(
            ["git", "merge-base", "HEAD", "main"],  # noqa: S607
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:  # noqa: S110
        pass
    return None


def _recompute_baseline_for_gate(
    step: WorkflowStep,
    worktree_path: str,
    gate_name: str,
    command: str,
    parser: Callable[[str], Fingerprint],
) -> Fingerprint | None:
    """Recompute baseline fingerprint for a single gate after rebase detection."""
    from orch.daemon.batch_manager import _agent_subprocess_env

    try:
        result = subprocess.run(  # noqa: S602
            command,
            shell=True,
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=300,
            env=_agent_subprocess_env(),
        )
        output = result.stdout + result.stderr
        return parser(output)
    except Exception as e:
        logger.warning(
            "[F-00061] Baseline recompute failed for %s/%s (gate=%s): %s",
            step.work_item_id,
            step.step_id,
            gate_name,
            e,
        )
        return None


def _qv_findings_legacy(db: Session, step: WorkflowStep, _worktree_path: str) -> str:
    """Legacy QV findings extraction without baseline subtraction."""
    latest_run = db.execute(
        select(StepRun)
        .where(
            StepRun.step_id == step.id,
            StepRun.status.in_([RunStatus.failed, RunStatus.timeout]),
        )
        .order_by(StepRun.run_number.desc())
        .limit(1)
    ).scalar_one_or_none()

    parts: list[str] = []

    if latest_run and latest_run.error_message:
        parts.append(f"**Error**: {latest_run.error_message}")

    if latest_run and latest_run.log_file:
        log_path = Path(latest_run.log_file)
        if log_path.exists():
            log_content = log_path.read_text()
            if len(log_content) > 3000:
                log_content = "...(truncated)...\n" + log_content[-3000:]
            parts.append(f"**Command output**:\n```\n{log_content}\n```")

    if latest_run and latest_run.log_content and not parts:
        parts.append(f"**Log content**:\n```\n{latest_run.log_content[-3000:]}\n```")

    if parts:
        return "\n\n".join(parts)

    return "Quality validation failed — check the command output for errors."


def _format_qv_findings_from_delta(delta: Fingerprint, latest_run: StepRun | None) -> str:
    """Format the delta (subtraction result) as findings string."""
    parts: list[str] = []

    if latest_run and latest_run.error_message:
        parts.append(f"**Error**: {latest_run.error_message}")

    failure_lines = []
    for f in delta.failures:
        failure_lines.append(f"  [{f.kind}] {f.key}")

    unparseable_lines = []
    for u in delta.unparseable:
        unparseable_lines.append(f"  {u}")

    if failure_lines or unparseable_lines:
        blocks = []
        if failure_lines:
            blocks.append("**New Failures**:\n" + "\n".join(failure_lines))
        if unparseable_lines:
            blocks.append(
                "**Unparseable output** (always surfaces):\n" + "\n".join(unparseable_lines)
            )
        parts.append("\n".join(blocks))

    if parts:
        return "\n\n".join(parts)

    return "Quality validation failed — check the command output for errors."


def _extract_mandatory_findings(content: str) -> str:
    """Extract CRITICAL/HIGH/MEDIUM-fixable findings from review report content.

    Looks for markdown ### headings with severity keywords and captures the
    content of each finding block.
    """
    # Try JSON mandatory_fix_count first — if 0, nothing to fix
    m = re.search(r'"mandatory_fix_count"\s*:\s*(\d+)', content)
    if m and int(m.group(1)) == 0:
        return ""

    # Extract ### Finding blocks with mandatory severities
    pattern = r"(###\s+.*(?:CRITICAL|HIGH|MEDIUM\s*[\(\[]fixable[\)\]]).*?)(?=\n###\s|\n##\s|\Z)"
    matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
    if matches:
        return "\n\n".join(m.strip() for m in matches)

    # If we can't parse findings but there's content, return a summary
    verdict_m = re.search(r'"verdict"\s*:\s*"([^"]+)"', content, re.IGNORECASE)
    if verdict_m and verdict_m.group(1).upper() not in ("PASS", "PASS_WITH_NOTES"):
        return content[:2000]  # Return truncated report as context

    return ""


# ---------------------------------------------------------------------------
# Internal: fix prompt generation
# ---------------------------------------------------------------------------


def _generate_fix_prompt(
    step: WorkflowStep,
    worktree_path: str,
    cycle_number: int,
    findings: str,
    max_cycles: int,
    prior_failure_reason: str | None = None,
) -> Path | None:
    """Generate a fix prompt from the template or inline, write to worktree."""
    item_id = step.work_item_id
    step_id = step.step_id

    # Build the prompt content — QV and browser steps get step-specific prompts
    if step.step_type == StepType.quality_validation:
        gate_command = _get_gate_command(step, worktree_path)
        prompt = _build_qv_fix_prompt_content(
            item_id, step_id, cycle_number, findings, max_cycles, gate_command
        )
    elif step.step_type == StepType.browser_verification:
        prompt = _build_browser_fix_prompt_content(
            item_id,
            step_id,
            cycle_number,
            findings,
            max_cycles,
            prior_failure_reason=prior_failure_reason,
        )
    else:
        prompt = _build_fix_prompt_content(
            item_id,
            step_id,
            cycle_number,
            findings,
            max_cycles,
        )

    # Write to a separate fix-cycles directory (NOT prompts/ — review agents scan that)
    prompt_dir = Path(worktree_path) / "ai-dev" / "active" / item_id / "fix-cycles"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = prompt_dir / f"{item_id}_{step_id}_FIX_cycle{cycle_number}_prompt.md"
    prompt_file.write_text(prompt)

    return prompt_file


def _get_gate_command(step: WorkflowStep, worktree_path: str) -> str:
    """Read the gate command from the workflow manifest for a QV step."""
    import json  # noqa: PLC0415

    manifest_path = (
        Path(worktree_path) / "ai-dev" / "active" / step.work_item_id / "workflow-manifest.json"
    )
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        for s in manifest.get("steps", []):
            if s.get("step") == step.step_id:
                return str(s.get("command", ""))
    return ""


def _build_qv_fix_prompt_content(
    item_id: str,
    step_id: str,
    cycle_number: int,
    findings: str,
    max_cycles: int,
    gate_command: str,
) -> str:
    """Build a fix prompt for a quality validation failure."""
    escalation = ""
    if cycle_number == max_cycles:
        escalation = (
            f"\n\n**ESCALATION**: This is the FINAL fix cycle ({cycle_number}/{max_cycles}). "
            "If you cannot resolve all issues, clearly document which remain and why."
        )

    command_hint = ""
    if gate_command:
        command_hint = (
            f"\n\n## Gate Command\n\n"
            f"The quality gate that failed runs:\n```bash\n{gate_command}\n```\n\n"
            f"After applying fixes, re-run this command to verify the issues are resolved.\n"
        )

    return (
        f"# {item_id} {step_id} QV Fix Cycle {cycle_number}/{max_cycles}\n\n"
        f"Quality gate {step_id} for work item {item_id} failed. "
        f"Fix the issues below so the gate passes on re-run.\n\n"
        f"## Errors to Fix\n\n{findings}\n"
        f"{command_hint}\n"
        f"## Constraints\n\n"
        f"1. **Only fix the reported errors.** Do not refactor unrelated code.\n"
        f"2. **Preserve existing behavior.** Fixes must not break working functionality.\n"
        f"3. **Follow project conventions.** Read `CLAUDE.md` for patterns.\n"
        f"4. **Run the gate command after every fix** to verify resolution.\n"
        f"{escalation}\n\n"
        f"**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. "
        f"Simply apply the fixes and exit. The orchestrator handles the rest.\n"
    )


def _build_browser_fix_prompt_content(
    item_id: str,
    step_id: str,
    cycle_number: int,
    findings: str,
    max_cycles: int,
    prior_failure_reason: str | None = None,
) -> str:
    """Build a fix prompt for a browser_verification failure.

    The V(n) FAILED messages and the report's root-cause section point at a
    real code defect (template/router/CLI). The fix agent applies the minimum
    patch; the daemon re-launches the browser step, which rebuilds the E2E
    stack with ``docker compose up --build`` and re-runs V1..V(n).

    If ``prior_failure_reason`` starts with ``ENV_DATA_MISSING:`` or similar
    "environmental" prefixes, the prompt adds a section that forces the
    agent to distinguish real env gaps (write a fixture / fix the test
    harness) from code defects hiding behind the label.
    """
    escalation = ""
    if cycle_number == max_cycles:
        escalation = (
            f"\n\n**ESCALATION**: This is the FINAL browser fix cycle "
            f"({cycle_number}/{max_cycles}). If you cannot resolve every failing "
            "verification, document which remain and why so the human reviewer "
            "can act on the evidence."
        )

    env_suspicion_block = ""
    if prior_failure_reason:
        stripped = prior_failure_reason.lstrip().upper()
        if stripped.startswith((_ENV_DATA_MISSING_PREFIX.upper(), "ENVIRONMENT:", "ENV:")):
            env_suspicion_block = (
                "\n## The previous agent claimed this was environmental\n\n"
                "The previous run's `--reason` was:\n\n"
                f"> {prior_failure_reason.strip()}\n\n"
                "Six of the last six genuine blockers on browser_verification "
                "steps were **code defects misdiagnosed as environmental** "
                "(wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, "
                "`/api/show` missing, `_run_qa_in_thread` swallowing exceptions, "
                "Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). "
                "Start by *assuming the previous classification is wrong*:\n\n"
                "1. Re-read the verification log for HTTP 5xx, pydantic "
                "   `ValidationError`, unhandled exceptions in stderr, or "
                "   `event: done` with zero tokens — all are code defects.\n"
                "2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not "
                "   `orch.db.session.SessionLocal`) for any E2E DB writes. "
                "   If SessionLocal appears in the failure log, it wrote to "
                "   the live orchestration DB and the dashboard under test "
                "   never saw the row — fix the prompt / test methodology.\n"
                "3. If the failure is genuinely environmental (missing seed "
                "   rows, missing daemon-driven state transitions), write "
                f"   `ai-dev/active/{item_id}/e2e_fixtures/NNN_<name>.py` "
                "   exporting `def seed(db: Session) -> None`. The "
                "   E2E stack loads these at bring-up. Do NOT add ad-hoc "
                "   inserts from the agent subprocess.\n"
                "4. If the test harness itself is wrong (e.g. a V step that "
                "   can't be satisfied in playwright-cli's session model, a "
                "   stub that doesn't speak the client's contract), fix the "
                "   harness. Prompts under `ai-dev/active/{item_id}/prompts/` "
                "   and fixtures under `scripts/` are in-scope.\n"
            )

    return (
        f"# {item_id} {step_id} Browser Verification Fix Cycle "
        f"{cycle_number}/{max_cycles}\n\n"
        f"The end-to-end browser verification for step {step_id} of work item "
        f"{item_id} failed. The qv-browser agent ran V1..V(n) against the "
        f"isolated E2E stack (dashboard + DB built from this worktree) and "
        f"reported code defects. Apply the minimum patch to make every failing "
        f"V pass; the daemon will rebuild the E2E stack and re-run the browser "
        f"checks.\n\n"
        f"## Browser Verification Report\n\n{findings}\n"
        f"{env_suspicion_block}"
        f"\n## Where to look\n\n"
        f"1. Read the **Issues Found** section above for a root-cause diagnosis "
        f"and `file:line` references. Trust it and start there.\n"
        f"2. Screenshots are under "
        f"`ai-dev/active/{item_id}/evidences/post/` — open the ones named in "
        f"the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.\n"
        f"3. The failing Vs map to files typically in:\n"
        f"   - `dashboard/templates/**` — if the UI rendered the wrong element\n"
        f"   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment\n"
        f"   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message\n"
        f"   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong\n"
        f"   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the "
        f"code-under-test's contract\n"
        f"   - `ai-dev/active/{item_id}/e2e_fixtures/` — if the E2E seed is "
        f"missing rows the V step needs\n\n"
        f"## Constraints\n\n"
        f"1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.\n"
        f"2. **Preserve existing behavior** for every V that already passed — "
        f"the report table flags passing Vs; do not regress them.\n"
        f"3. **Follow project conventions.** Read `CLAUDE.md` for patterns.\n"
        f"4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or "
        f"invoke `playwright-cli` — the orchestrator owns the E2E stack and "
        f"will rebuild it before the next browser run.\n"
        f"5. Run any fast unit tests near the code you touched to catch "
        f"regressions before the expensive E2E re-run.\n"
        f"{escalation}\n\n"
        f"**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. "
        f"Simply apply the fixes and exit. The orchestrator re-launches the "
        f"browser verification automatically.\n"
    )


def _build_fix_prompt_content(
    item_id: str,
    step_id: str,
    cycle_number: int,
    findings: str,
    max_cycles: int,
) -> str:
    """Build the fix prompt content."""
    escalation = ""
    if cycle_number == max_cycles:
        escalation = (
            f"\n\n**ESCALATION**: This is the FINAL fix cycle ({cycle_number}/{max_cycles}). "
            "If you cannot resolve all findings, clearly document which findings remain "
            "and why they could not be fixed."
        )

    return (
        f"# {item_id} {step_id} Fix Cycle {cycle_number}/{max_cycles}\n\n"
        f"The code review for step {step_id} of work item {item_id} found issues "
        f"that must be fixed.\n\n"
        f"## Findings to Fix\n\n{findings}\n\n"
        f"## Constraints\n\n"
        f"1. **Only fix the flagged issues.** Do not refactor unrelated code.\n"
        f"2. **Preserve existing behavior.** Fixes must not break working functionality.\n"
        f"3. **Follow project conventions.** Read `CLAUDE.md` for patterns.\n"
        f"4. **Run tests after every fix.** Ensure no regressions.\n"
        f"{escalation}\n\n"
        f"## Instructions\n\n"
        f"1. Read the findings above carefully\n"
        f"2. Apply the minimum changes needed to resolve each finding\n"
        f"3. Run tests to verify no regressions\n"
        f"4. Exit when done — the daemon will detect completion and re-run the review\n\n"
        f"**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. "
        f"Simply apply the fixes and exit. The orchestrator handles the rest.\n"
    )


# ---------------------------------------------------------------------------
# Internal: fix agent launch
# ---------------------------------------------------------------------------


def _launch_fix_agent(
    step: WorkflowStep,
    worktree_path: str,
    prompt_path: Path | None,
    project_config: ProjectConfig,
    config: DaemonConfig,  # noqa: ARG001
    cycle_number: int,
) -> tuple[int, Path, int]:
    """Launch the fix agent subprocess. Returns (pid, log_file, timeout_secs)."""
    from orch.daemon.batch_manager import _build_agent_env  # noqa: PLC0415
    from orch.daemon.step_monitor import get_timeout  # noqa: PLC0415

    cli_tool = project_config.cli_tool
    item_id = step.work_item_id
    step_id = step.step_id
    fix_step_type = _FIX_TIMEOUT_MAP.get(step.step_type, "code_review_fix")
    timeout = get_timeout(project_config, fix_step_type)

    # Build command
    if cli_tool == "opencode":
        # Read the prompt file and pass to opencode
        prompt_text = prompt_path.read_text() if prompt_path else "Fix the code review findings."
        # Write to a temp file for opencode
        tmp_prompt = Path(worktree_path) / ".tmp" / f"{item_id}_{step_id}_fix{cycle_number}.prompt"
        tmp_prompt.parent.mkdir(parents=True, exist_ok=True)
        tmp_prompt.write_text(prompt_text)
        command = f"opencode run '{tmp_prompt}'"
    else:
        if prompt_path and prompt_path.exists():
            prompt_text = prompt_path.read_text()
        else:
            prompt_text = "Fix the code review findings."
        tmp_prompt = Path(worktree_path) / ".tmp" / f"{item_id}_{step_id}_fix{cycle_number}.prompt"
        tmp_prompt.parent.mkdir(parents=True, exist_ok=True)
        tmp_prompt.write_text(prompt_text)
        command = f'claude -p "$(cat {tmp_prompt})" --dangerously-skip-permissions'

    # Log file
    log_dir = Path(worktree_path) / "ai-dev" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{item_id}_{step_id}_fix{cycle_number}.log"

    # Build environment
    env = _build_agent_env(cli_tool, item_id, worktree_path)

    # Launch
    if cli_tool == "opencode":
        shell_command = f'script -qec "timeout {timeout} {command}" /dev/null'
    else:
        shell_command = f"timeout {timeout} {command}"

    proc = subprocess.Popen(  # noqa: S602
        shell_command,
        shell=True,
        cwd=worktree_path,
        stdin=subprocess.DEVNULL,
        stdout=Path(log_file).open("w"),  # noqa: SIM115
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )

    logger.info(
        "Fix agent launched: %s/%s cycle %d (PID %d, timeout %ds)",
        item_id,
        step_id,
        cycle_number,
        proc.pid,
        timeout,
    )

    return proc.pid, log_file, timeout


# ---------------------------------------------------------------------------
# Internal: process helpers
# ---------------------------------------------------------------------------


def _is_pid_alive(pid: int | None) -> bool:
    from orch.daemon.step_monitor import _is_pid_alive as _monitor_is_alive  # noqa: PLC0415

    return _monitor_is_alive(pid)


def _kill_pid(pid: int | None) -> None:
    if pid is None:
        return
    from orch.daemon.step_monitor import kill_process_group  # noqa: PLC0415

    kill_process_group(pid)


def _emit_event(
    db: Session,
    project_id: str,
    event_type: str,
    entity_id: str | None,
    entity_type: str | None = None,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=entity_id,
        entity_type=entity_type,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(event)


def _parse_and_store_fix_summary(cycle: Any) -> None:
    """Read fix_summary from the fix agent's JSON log file and store it on the cycle.

    Silently handles all errors (missing key, malformed JSON, file not found) so the
    caller never throws — the fix summary is best-effort only.
    """
    import json  # noqa: PLC0415

    meta = cycle.fix_metadata
    if not meta:
        return
    log_file = meta.get("log_file")
    if not log_file:
        return

    try:
        content = Path(log_file).read_text(encoding="utf-8")
    except OSError:
        return

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return

    summary = data.get("fix_summary")
    if summary is None:
        cycle.fix_summary = None
        return
    if not isinstance(summary, str):
        return
    if not summary or not summary.strip():
        return

    if len(summary) > _MAX_FIX_SUMMARY_LEN:
        summary = summary[:_MAX_FIX_SUMMARY_LEN]
    cycle.fix_summary = summary
