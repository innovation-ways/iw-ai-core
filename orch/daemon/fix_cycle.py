"""Fix cycle management — automatic code review fix loops.

When a code_review or code_review_final step fails (agent found mandatory
findings), the daemon creates a FixCycle, launches a fix agent, and after
completion resets the review step to pending so it re-runs automatically.
Loops up to fix_cycle_max (default 5) times before giving up.
"""

from __future__ import annotations

import logging
import os
import re
import signal
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
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.config import DaemonConfig
    from orch.daemon.project_registry import ProjectConfig

logger = logging.getLogger(__name__)

# Step types that can trigger fix cycles
_FIXABLE_STEP_TYPES = frozenset(
    {StepType.code_review, StepType.code_review_final, StepType.quality_validation}
)

_TRIGGER_MAP: dict[StepType, FixTrigger] = {
    StepType.code_review: FixTrigger.code_review,
    StepType.code_review_final: FixTrigger.code_review_final,
    StepType.quality_validation: FixTrigger.quality_validation,
}

_FIX_TIMEOUT_MAP: dict[StepType, str] = {
    StepType.code_review: "code_review_fix",
    StepType.code_review_final: "code_review_fix_final",
    StepType.quality_validation: "qv_fix",
}

_DEFAULT_FIX_CYCLE_MAX = 5


# ---------------------------------------------------------------------------
# Public API (called from batch_manager)
# ---------------------------------------------------------------------------


def should_attempt_fix(
    db: Session,
    step: WorkflowStep,
    project_config: ProjectConfig,
) -> bool:
    """Return True if this failed step is a review that can be auto-fixed."""
    if step.step_type not in _FIXABLE_STEP_TYPES:
        return False

    max_cycles = project_config.config.get("fix_cycle_max", _DEFAULT_FIX_CYCLE_MAX)
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

    max_cycles = project_config.config.get("fix_cycle_max", _DEFAULT_FIX_CYCLE_MAX)
    existing_count = db.query(FixCycle).filter(FixCycle.step_id == step.id).count()
    cycle_number = existing_count + 1

    # Get the review findings from the latest failed StepRun
    findings = _get_review_findings(db, step, worktree_path)

    # Generate fix prompt
    prompt_path = _generate_fix_prompt(
        step,
        worktree_path,
        cycle_number,
        findings,
        max_cycles,
    )

    # Transition step: failed → needs_fix
    step.status = StepStatus.needs_fix
    step.started_at = None
    step.completed_at = None

    # Create FixCycle record
    trigger = _TRIGGER_MAP[step.step_type]
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


def _get_review_findings(db: Session, step: WorkflowStep, worktree_path: str) -> str:
    """Extract findings from the report file, StepRun error_message, or log content."""
    # For QV steps, prefer the step_run error and log content (command output)
    if step.step_type == StepType.quality_validation:
        return _get_qv_findings(db, step, worktree_path)

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


def _get_qv_findings(db: Session, step: WorkflowStep, worktree_path: str) -> str:
    """Extract quality validation findings from step_run error/log content."""
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

    # Try to read the log file for full command output
    if latest_run and latest_run.log_file:
        log_path = Path(latest_run.log_file)
        if log_path.exists():
            log_content = log_path.read_text()
            # Truncate to last 3000 chars to keep prompt manageable
            if len(log_content) > 3000:
                log_content = "...(truncated)...\n" + log_content[-3000:]
            parts.append(f"**Command output**:\n```\n{log_content}\n```")

    # Try log_content stored in DB
    if latest_run and latest_run.log_content and not parts:
        parts.append(f"**Log content**:\n```\n{latest_run.log_content[-3000:]}\n```")

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
) -> Path | None:
    """Generate a fix prompt from the template or inline, write to worktree."""
    item_id = step.work_item_id
    step_id = step.step_id

    # Build the prompt content — QV steps get a command-aware prompt
    if step.step_type == StepType.quality_validation:
        gate_command = _get_gate_command(step, worktree_path)
        prompt = _build_qv_fix_prompt_content(
            item_id, step_id, cycle_number, findings, max_cycles, gate_command
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
    prompt_dir = Path(worktree_path) / "ai-dev" / "design" / "active" / item_id / "fix-cycles"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = prompt_dir / f"{item_id}_{step_id}_FIX_cycle{cycle_number}_prompt.md"
    prompt_file.write_text(prompt)

    return prompt_file


def _get_gate_command(step: WorkflowStep, worktree_path: str) -> str:
    """Read the gate command from the workflow manifest for a QV step."""
    import json  # noqa: PLC0415

    manifest_path = (
        Path(worktree_path)
        / "ai-dev"
        / "design"
        / "active"
        / step.work_item_id
        / "workflow-manifest.json"
    )
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        for s in manifest.get("steps", []):
            if s.get("step") == step.step_id:
                return s.get("command", "")
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
    try:
        os.kill(pid, signal.SIGTERM)
        logger.info("Sent SIGTERM to fix agent PID %d", pid)
    except ProcessLookupError:
        pass


def _emit_event(
    db: Session,
    project_id: str,
    event_type: str,
    entity_id: str | None,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=entity_id,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(event)
