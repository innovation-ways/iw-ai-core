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
    WorkItem,
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
# Bumped to 5 from 3 after CR-00036 validation showed that 3 cycles was
# insufficient for realistic browser fix loops.
_DEFAULT_BROWSER_FIX_CYCLE_MAX = 5

# Per-gate-type budgets for quality_validation steps.
# QV fix cycles vary significantly in cost/complexity — lint/format agents
# are fast and mechanical (3 cycles is plenty), integration tests are slow
# and may require deeper analysis (7 cycles allows convergence).
_DEFAULT_QV_GATE_BUDGETS: dict[str, int] = {
    "lint": 3,
    "format": 3,
    "typecheck": 3,
    "unit-tests": 5,
    "integration-tests": 7,
}


# ---------------------------------------------------------------------------
# Internal: configured cycle limits
# ---------------------------------------------------------------------------


def _max_cycles_for(
    step_type: StepType,
    project_config: ProjectConfig,
    step: WorkflowStep | None = None,
) -> int:
    """Resolve max fix cycles for a step type.

    For ``qv_gate`` steps, a finer-grained per-gate budget is applied:
    lint/format/typecheck → 3, unit-tests → 5, integration-tests → 7.
    Per-project overrides can be set in projects.toml via
    ``qv_fix_cycle_max = { lint = 3, "unit-tests" = 5 }``
    (merged into the project's config dict by _build_project_config).

    For ``browser_verification`` steps, ``browser_fix_cycle_max`` applies
    (default 5).  All other step types use ``fix_cycle_max`` (default 5).
    """
    if step_type is StepType.browser_verification:
        return int(
            project_config.config.get("browser_fix_cycle_max", _DEFAULT_BROWSER_FIX_CYCLE_MAX)
        )

    if step is not None and step_type is StepType.quality_validation and step.gate is not None:
        # Per-project override dict takes precedence over built-in defaults.
        per_project: dict[str, int] = project_config.qv_fix_cycle_max
        gate = step.gate
        if gate in per_project:
            return per_project[gate]
        if gate in _DEFAULT_QV_GATE_BUDGETS:
            return _DEFAULT_QV_GATE_BUDGETS[gate]

    return int(project_config.config.get("fix_cycle_max", _DEFAULT_FIX_CYCLE_MAX))


# ---------------------------------------------------------------------------
# Public API (called from batch_manager)
# ---------------------------------------------------------------------------


_ENV_DATA_MISSING_PREFIX = "ENV_DATA_MISSING:"
_SPEC_MISMATCH_PREFIX = "SPEC_MISMATCH:"


def is_spec_mismatch_failure(reason: str | None) -> bool:
    """Return True when a failure reason is prefixed with ``SPEC_MISMATCH:``.

    The check is case-insensitive and ignores leading whitespace so that minor
    agent output variations don't prevent detection.  A SPEC_MISMATCH failure
    means the V step verifies behaviour that the design doc explicitly excludes;
    no code fix can satisfy it — the step must be left failed for human review.
    """
    if not reason:
        return False
    return reason.lstrip().upper().startswith(_SPEC_MISMATCH_PREFIX.upper())


def handle_spec_mismatch_escalation(
    db: Session,
    step: WorkflowStep,
    project_id: str,
    failure_reason: str | None,
) -> None:
    """Record a spec-mismatch escalation event and leave the step in ``failed``.

    Called by batch_manager when a browser_verification step reports
    ``SPEC_MISMATCH:``.  The step status is NOT changed (it stays ``failed``
    so the human reviewer sees it as a blocking issue).  No FixCycle is
    created — there is nothing a code-fix agent can do.

    A ``DaemonEvent`` of type ``spec_mismatch_escalation`` is emitted so the
    human reviewer can identify and act on it from the dashboard or the events
    table.
    """
    _emit_event(
        db,
        project_id,
        "spec_mismatch_escalation",
        step.work_item_id,
        "work_item",
        (
            f"Step {step.step_id} failed with SPEC_MISMATCH — "
            "verification asks for something the design doc explicitly excludes. "
            "Human review required; no fix cycle will be attempted."
        ),
        {
            "step_id": step.step_id,
            "failure_reason": failure_reason or "",
        },
    )
    db.commit()

    logger.warning(
        "[%s] SPEC_MISMATCH escalation for %s/%s: %s",
        project_id,
        step.work_item_id,
        step.step_id,
        failure_reason or "(no reason)",
    )


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

    ``SPEC_MISMATCH:`` failures are a different category: the V step asks for
    something the design doc explicitly excludes.  No code fix can satisfy it,
    so the fix cycle is skipped entirely and a ``spec_mismatch_escalation``
    event is emitted (by ``handle_spec_mismatch_escalation`` in batch_manager).

    self_assess steps are soft — failures never trigger fix cycles; the
    item proceeds to merge regardless.
    """
    from orch.self_assess import is_self_assess_step  # noqa: PLC0415

    if is_self_assess_step(step.step_type):
        return False
    if step.step_type not in _FIXABLE_STEP_TYPES:
        return False

    # SPEC_MISMATCH: the verification asks for something the design doc
    # excludes.  No fix agent can resolve this — escalate to human review.
    if is_spec_mismatch_failure(_latest_failure_reason(db, step)):
        return False

    max_cycles = _max_cycles_for(step.step_type, project_config, step=step)
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

    # B.3: Aggregate per-work-item budget — backstop independent of per-step caps.
    # Prevents pathological cascades from burning unbounded total cycles even when
    # no single step exhausts its own budget.
    aggregate_max = project_config.aggregate_fix_cycle_max
    aggregate_used = (
        db.query(FixCycle)
        .join(WorkflowStep, FixCycle.step_id == WorkflowStep.id)
        .filter(WorkflowStep.work_item_id == step.work_item_id)
        .filter(WorkflowStep.project_id == step.project_id)
        .count()
    )
    if aggregate_used >= aggregate_max:
        logger.warning(
            "Aggregate fix-cycle budget exhausted (%d/%d) for work item %s/%s — "
            "halting recovery on step %s",
            aggregate_used,
            aggregate_max,
            step.project_id,
            step.work_item_id,
            step.step_id,
        )
        _emit_event(
            db,
            step.project_id,
            "aggregate_budget_exhausted",
            step.work_item_id,
            "work_item",
            (
                f"Work item exhausted aggregate fix-cycle budget "
                f"({aggregate_used}/{aggregate_max}); halting recovery on step {step.step_id}."
            ),
            {
                "aggregate_used": aggregate_used,
                "aggregate_max": aggregate_max,
                "step_id": step.step_id,
                "step_type": step.step_type.value if step.step_type else None,
            },
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

    max_cycles = _max_cycles_for(step.step_type, project_config, step=step)
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
    pid, log_file, timeout, _step_run = _launch_fix_agent(
        db,
        step,
        worktree_path,
        prompt_path,
        project_config,
        config,
        cycle_number,
    )

    # Capture the worktree HEAD SHA before the fix agent runs.
    # Used by Change 2 (_files_changed_by_fix_cycle) to diff the patch
    # against HEAD after the agent exits.  Defensive: failure is non-fatal.
    start_sha: str | None = None
    try:
        sha_result = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if sha_result.returncode == 0:
            start_sha = sha_result.stdout.strip() or None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[%s] Could not capture start_sha for fix cycle %d/%d: %s",
            project_id,
            cycle_number,
            max_cycles,
            exc,
        )

    now = datetime.now(UTC)
    fix_cycle.status = FixStatus.in_progress
    fix_cycle.started_at = now
    fix_cycle.fix_metadata = {
        "pid": pid,
        "log_file": str(log_file),
        "timeout_secs": timeout,
        "worktree_path": worktree_path,
        "start_sha": start_sha,
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


def _cascade_reset_upstream_qv_gates(
    db: Session,
    cycle: FixCycle,  # noqa: ARG001 — kept for hook-point symmetry / future use
    failing_step: WorkflowStep,
    project_id: str,  # noqa: ARG001 — kept for hook-point symmetry / future use
) -> list[str]:
    """Reset every previously-completed QV gate that runs upstream of
    ``failing_step`` in the same work item, so the daemon re-runs them
    against the patched code.

    Returns the list of reset step_ids for daemon-event payload.

    No-op when the failing step is not itself a QV gate (quality_validation or
    browser_verification) — non-QV review fixes don't invalidate upstream QV
    results because no QV gate has run yet at that point in the canonical
    pipeline.
    """
    if failing_step.step_type not in {StepType.quality_validation, StepType.browser_verification}:
        return []

    upstream_gates = (
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.work_item_id == failing_step.work_item_id,
            WorkflowStep.project_id == failing_step.project_id,
            WorkflowStep.step_type.in_(
                [StepType.quality_validation, StepType.browser_verification]
            ),
            WorkflowStep.step_id < failing_step.step_id,
            WorkflowStep.status == StepStatus.completed,
            WorkflowStep.id != failing_step.id,
        )
        .all()
    )

    reset_ids: list[str] = []
    for gate in upstream_gates:
        gate.status = StepStatus.pending
        gate.started_at = None
        gate.completed_at = None
        reset_ids.append(gate.step_id)

    return reset_ids


def _peek_cascade_reset_ids(
    db: Session,
    failing_step: WorkflowStep,
    project_id: str,
) -> list[str]:
    """Return the step_ids that WOULD be cascade-reset for failing_step,
    without mutating any WorkflowStep objects.

    Used by the thrashing detector to preview the reset-set so that
    _detect_thrashing can include the current (in-flight) cascade in
    its similarity window — without touching DB state.
    """
    if failing_step.step_type not in {StepType.quality_validation, StepType.browser_verification}:
        return []

    upstream_gates = (
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.work_item_id == failing_step.work_item_id,
            WorkflowStep.project_id == project_id,
            WorkflowStep.step_type.in_(
                [StepType.quality_validation, StepType.browser_verification]
            ),
            WorkflowStep.step_id < failing_step.step_id,
            WorkflowStep.status == StepStatus.completed,
            WorkflowStep.id != failing_step.id,
        )
        .all()
    )
    return [gate.step_id for gate in upstream_gates]


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two sets. Returns 0.0 when both are empty."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _detect_thrashing(
    db: Session,
    work_item_id: str,
    current_trigger_step_id: str,
    current_reset_set: set[str],
    *,
    threshold: int = 3,
    jaccard_min: float = 0.5,
) -> bool:
    """Return True if the current cascade event indicates thrashing.

    Thrashing pattern: the same trigger_step has fired >=``threshold`` cascades
    within this work item, AND each consecutive cascade's reset_set has
    Jaccard similarity >=``jaccard_min`` with the previous.

    Reads DaemonEvents of type 'cascaded_replay_after_fix' for this work item,
    filters to those with trigger_step_id == current_trigger_step_id, and
    inspects reset_step_ids in event_metadata. Compares consecutive pairs
    including the current (in-flight) cascade that has not yet been persisted.

    The check includes the *current* cascade by prepending current_reset_set
    to the historical list, so a threshold of 3 fires when the historical
    list has >=2 previous cascades (total = 2 + current = 3).
    """
    past_events = (
        db.query(DaemonEvent)
        .filter(
            DaemonEvent.entity_id == work_item_id,
            DaemonEvent.entity_type == "work_item",
            DaemonEvent.event_type == "cascaded_replay_after_fix",
        )
        .order_by(DaemonEvent.created_at)
        .all()
    )

    # Collect reset_sets for the same trigger step (historical only).
    historical_sets: list[set[str]] = []
    for event in past_events:
        meta = event.event_metadata or {}
        if meta.get("trigger_step_id") != current_trigger_step_id:
            continue
        raw_ids = meta.get("reset_step_ids", [])
        historical_sets.append(set(raw_ids) if isinstance(raw_ids, list) else set())

    # Build the full sequence: historical + current cascade
    all_sets = historical_sets + [current_reset_set]
    cascade_count = len(all_sets)

    if cascade_count < threshold:
        return False

    # Check that every consecutive pair in the window ending at the current
    # cascade has sufficient Jaccard overlap.
    # We only need to verify the last ``threshold`` entries (inclusive of current).
    window = all_sets[-(threshold):]
    return all(_jaccard(window[i], window[i + 1]) >= jaccard_min for i in range(len(window) - 1))


def _complete_fix_cycle(
    db: Session,
    cycle: FixCycle,
    project_id: str,
    now: datetime,
    project_config: ProjectConfig | None = None,
) -> None:
    """Mark fix cycle as completed and reset the review step to pending.

    ``project_config`` is optional for backwards compatibility with callers
    that pre-date the thrashing detector (B.2). When None the thrashing check
    is skipped (safe default — never raises).
    """
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

        # B.2 — thrashing detection: probe what the cascade reset-set would be
        # WITHOUT yet mutating any upstream step.  When thrashing is detected,
        # the upstream gates are left in their current state (no cascade reset),
        # Change 2 review-replay is also suppressed, and we emit a dedicated
        # event that tells the operator to intervene.
        potential_reset_ids = _peek_cascade_reset_ids(db, step, project_id)
        thrashing = False
        if potential_reset_ids and project_config is not None:
            thrashing = _detect_thrashing(
                db,
                step.work_item_id,
                step.step_id,
                set(potential_reset_ids),
                threshold=project_config.cascade_thrashing_threshold,
                jaccard_min=project_config.cascade_thrashing_jaccard_min,
            )

        if thrashing:
            # Count how many past cascades the same trigger has fired.
            past_cascade_count = (
                db.query(DaemonEvent)
                .filter(
                    DaemonEvent.entity_id == step.work_item_id,
                    DaemonEvent.entity_type == "work_item",
                    DaemonEvent.event_type == "cascaded_replay_after_fix",
                )
                .count()
            )
            _emit_event(
                db,
                project_id,
                "cascade_thrashing_detected",
                step.work_item_id,
                "work_item",
                (
                    f"Thrashing detected: {step.step_id} has triggered {past_cascade_count + 1} "
                    f"cascades with overlapping reset-sets {potential_reset_ids}. "
                    "Automatic recovery halted — manual review needed."
                ),
                {
                    "trigger_step_id": step.step_id,
                    "cascade_count": past_cascade_count + 1,
                    "reset_set": potential_reset_ids,
                    "recommendation": "halt automatic recovery; manual review needed",
                },
            )
            logger.warning(
                "[%s] Cascade thrashing detected for %s/%s after %d cascades — halting recovery",
                project_id,
                step.work_item_id,
                step.step_id,
                past_cascade_count + 1,
            )
        else:
            # Change 1: cascade-reset upstream QV gates so the daemon re-runs
            # them against the patched code.
            reset_step_ids = _cascade_reset_upstream_qv_gates(db, cycle, step, project_id)
            if reset_step_ids:
                _emit_event(
                    db,
                    project_id,
                    "cascaded_replay_after_fix",
                    step.work_item_id,
                    "work_item",
                    (
                        f"Fix cycle {cycle.cycle_number} on {step.step_id} → "
                        f"re-running upstream QV gates: {', '.join(reset_step_ids)}"
                    ),
                    {
                        "cycle_id": cycle.id,
                        "trigger_step_id": step.step_id,
                        "reset_step_ids": reset_step_ids,
                        "reason": "code_changed_by_fix_cycle",
                    },
                )

            # Change 2: re-run layer-specific code reviews for files touched by the fix.
            worktree_path = (cycle.fix_metadata or {}).get("worktree_path", "")
            if worktree_path:
                from pathlib import Path  # noqa: PLC0415

                from orch.daemon import review_mapping  # noqa: PLC0415

                changed_files = _files_changed_by_fix_cycle(cycle, worktree_path)
                if changed_files:
                    mapping = review_mapping.load_review_mapping(Path(worktree_path))
                    target_agents = review_mapping.review_agents_for(changed_files, mapping)
                    review_reset_ids = _reset_review_steps_for_agents(
                        db, step, target_agents, project_id
                    )
                    if review_reset_ids:
                        _emit_event(
                            db,
                            project_id,
                            "review_replay_after_fix",
                            step.work_item_id,
                            "work_item",
                            (
                                f"Fix touched {len(changed_files)} file(s) — "
                                f"re-running reviews: {', '.join(review_reset_ids)}"
                            ),
                            {
                                "cycle_id": cycle.id,
                                "trigger_step_id": step.step_id,
                                "changed_files": changed_files,
                                "reset_step_ids": review_reset_ids,
                                "reason": "code_changed_by_fix_cycle_in_layer",
                            },
                        )

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

    Note: step.report_file and step.report_content reflect run 1's agent-reported
    failure. Newer daemon-detected failures (where the StepRun has report_file=None
    but error_message is set) are prepended as the leading context so the fix agent
    sees the current blocking issue first. The original report is always preserved
    below as secondary context for V table reference.
    """
    content = None

    if step.report_file:
        report_path = Path(worktree_path) / step.report_file
        if report_path.exists():
            content = report_path.read_text()

    if content is None and step.report_content:
        content = step.report_content

    if content is not None:
        latest_failed = db.execute(
            select(StepRun)
            .where(
                StepRun.step_id == step.id,
                StepRun.status.in_([RunStatus.failed, RunStatus.timeout]),
            )
            .order_by(StepRun.run_number.desc())
            .limit(1)
        ).scalar_one_or_none()

        if latest_failed and not latest_failed.report_file and latest_failed.error_message:
            content = (
                f"## ⚠️ Most Recent Failure (run {latest_failed.run_number})\n\n"
                f"{latest_failed.error_message}\n\n"
                "---\n\n"
                "## Original Browser Report (for V table context)\n\n" + content
            )

        return _truncate(content, 8000)

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
        result = subprocess.run(  # noqa: S603
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
        result = subprocess.run(  # noqa: S602  # nosec B602
            command,
            shell=True,  # nosec B602  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true — trusted gate command from server-side step config used to recompute baseline fingerprint, no untrusted input on argv
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=900,
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


def _qv_findings_legacy(db: Session, step: WorkflowStep, worktree_path: str) -> str:
    """Legacy QV findings extraction without baseline subtraction.

    The qv-gate agent runs the gate command via its own Bash tool and writes
    the actual stdout (FAILED test names, ruff lines, etc.) into the report
    markdown — *not* into the daemon-managed StepRun.log_file, which only
    captures the agent's high-level chatter and ends up containing just the
    one-line `step-fail --reason` echo. So when picking findings to feed to
    the fix-cycle agent we prefer, in order:

    1. ``step.report_content`` (and ``step.report_file`` on disk) — the
       qv-gate report's "Output (tail)" section is the highest-fidelity
       record of what the gate actually produced.
    2. ``step_run.error_message`` — the human-readable failure reason.
    3. ``step_run.log_file`` / ``log_content`` as a last resort.
    """
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

    report_text = _read_step_report(step, worktree_path)
    if report_text:
        parts.append(f"**Gate report**:\n```\n{_tail_text(report_text, 3000)}\n```")
        # The report already carries the gate's stdout (FAILED test list, lint
        # lines, etc.). The daemon-managed log_file/log_content for QV steps is
        # almost always just a one-line `step-fail --reason` echo, so adding it
        # would only create a misleading second "Command output" block.
        return "\n\n".join(parts)

    if latest_run and latest_run.log_file:
        log_path = Path(latest_run.log_file)
        if log_path.exists():
            log_content = log_path.read_text()
            if log_content.strip() and not _is_reason_echo(log_content, latest_run.error_message):
                parts.append(f"**Command output**:\n```\n{_tail_text(log_content, 3000)}\n```")

    if (
        latest_run
        and latest_run.log_content
        and not any(p.startswith(("**Command output**", "**Gate report**")) for p in parts)
        and not _is_reason_echo(latest_run.log_content, latest_run.error_message)
    ):
        parts.append(f"**Log content**:\n```\n{_tail_text(latest_run.log_content, 3000)}\n```")

    if parts:
        return "\n\n".join(parts)

    return "Quality validation failed — check the command output for errors."


def _is_reason_echo(text: str, reason: str | None) -> bool:
    """True if ``text`` is just the ``step-fail --reason`` one-liner.

    The daemon log file for a QV step usually ends up with a single line like
    ``Failed I-00061 step S10: integration-tests failed: exit=2`` — that's the
    qv-gate agent's terminal output, not the gate's stdout. When the only
    thing in the log is that echo, treating it as "Command output" is
    misleading; we'd rather report nothing than nudge the fix agent toward
    fixing the echo.
    """
    if not reason:
        return False
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) > 200:
        return False
    return reason.strip() in stripped


def _tail_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return "...(truncated)...\n" + text[-limit:]


def _read_step_report(step: WorkflowStep, worktree_path: str) -> str | None:
    """Return the QV gate report content (DB column or file on disk), or None."""
    if step.report_content:
        return step.report_content
    if step.report_file:
        report_path = Path(step.report_file)
        if not report_path.is_absolute():
            report_path = Path(worktree_path) / step.report_file
        if report_path.exists():
            try:
                return report_path.read_text(encoding="utf-8")
            except OSError:
                return None
    return None


def _format_qv_findings_from_delta(delta: Fingerprint, latest_run: StepRun | None) -> str:
    """Format the delta (subtraction result) as findings string."""
    parts: list[str] = []

    if latest_run and latest_run.error_message:
        parts.append(f"**Error**: {latest_run.error_message}")

    failure_lines = []
    for f in delta.failures:
        failure_lines.append(f"  [{f.kind}] {f.key}")

    # Belt-and-suspenders: even though every parser already caps its own
    # `unparseable` list, re-cap here so a future parser change can't bloat the
    # fix-cycle prompt past execve's argv limit. (See I-00074.)
    from orch.daemon.qv_baseline import cap_unparseable  # noqa: PLC0415

    unparseable_lines = [f"  {u}" for u in cap_unparseable(list(delta.unparseable))]

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
# Internal: design-doc references for fix prompts (anti-drift)
# ---------------------------------------------------------------------------


_MAX_DESIGN_QUOTE_CHARS = 8000


def _find_design_doc(worktree_path: str, item_id: str) -> Path | None:
    """Locate the design doc for a work item under the worktree.

    Convention: ``ai-dev/active/<item_id>/<item_id>_*_Design.md`` (Issue,
    Feature, or Change-Request). Returns the first match or None.
    """
    base = Path(worktree_path) / "ai-dev" / "active" / item_id
    if not base.is_dir():
        return None
    for path in sorted(base.glob(f"{item_id}_*_Design.md")):
        if path.is_file():
            return path
    return None


def _extract_step_section(design_text: str, step_id: str) -> str | None:
    """Best-effort extract a step-specific section from the design doc.

    Looks for headings like ``### Detailed Fix Specification for S01``,
    ``### S01 — Frontend``, or ``### Step S01``. Returns the matched block
    (heading + body, up to the next same-or-higher heading) or None.
    Absence is non-fatal: callers fall back to linking the full doc.
    """
    if not design_text or not step_id:
        return None
    # Heading shapes, first hit wins. Multiline + DOTALL + IGNORECASE.
    candidates = (
        rf"(?ims)^(\#{{1,6}}\s+detailed\s+fix\s+specification\s+for\s+{step_id}\b[^\n]*\n.*?)"
        rf"(?=^\#{{1,6}}\s+|\Z)",
        rf"(?ims)^(\#{{1,6}}\s+{step_id}\b[^\n]*\n.*?)(?=^\#{{1,6}}\s+|\Z)",
        rf"(?ims)^(\#{{1,6}}\s+step\s+{step_id}\b[^\n]*\n.*?)(?=^\#{{1,6}}\s+|\Z)",
    )
    for pattern in candidates:
        match = re.search(pattern, design_text)
        if match:
            return match.group(1).strip()
    return None


def _build_design_doc_block(worktree_path: str, item_id: str, step_id: str) -> str:
    """Return a markdown section pointing the fix agent at the design doc.

    Always names the doc by absolute path so the agent can `Read` it. When a
    step-specific slice can be located, quotes it inline (truncated to
    ``_MAX_DESIGN_QUOTE_CHARS``). Returns an empty string when no design doc
    is found — callers must tolerate that case (legacy items, dry-run tests).
    """
    doc_path = _find_design_doc(worktree_path, item_id)
    if doc_path is None:
        return ""
    try:
        text = doc_path.read_text(encoding="utf-8")
    except OSError:
        return ""

    slice_text = _extract_step_section(text, step_id)
    quoted = ""
    if slice_text:
        body = slice_text[:_MAX_DESIGN_QUOTE_CHARS]
        truncation_note = (
            "\n\n*(slice truncated — read the full doc for the rest)*"
            if len(slice_text) > _MAX_DESIGN_QUOTE_CHARS
            else ""
        )
        quoted = (
            f"\n\n### Step-specific slice (verbatim from the doc above)\n\n"
            f"{body}{truncation_note}\n"
        )

    return (
        "## Design Doc — Source of Truth (READ FIRST)\n\n"
        "The design document for this work item is the authoritative spec for "
        "the change. Read it before applying any fix:\n\n"
        f"- **Path**: `{doc_path}`\n"
        "- Why this matters: prior fix cycles on this codebase have failed "
        "because the agent trusted the failure-report's *root-cause hypothesis* "
        "and drifted away from the design doc's explicit fix spec. **The design "
        "doc wins when the two disagree.**"
        f"{quoted}\n"
    )


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

    # Resolve design-doc reference once and pass to whichever builder handles
    # the step type. Empty string = no doc found (legacy or partial worktree).
    design_doc_block = _build_design_doc_block(worktree_path, item_id, step_id)

    # Build the prompt content — QV and browser steps get step-specific prompts
    if step.step_type == StepType.quality_validation:
        gate_command = _get_gate_command(step, worktree_path)
        prompt = _build_qv_fix_prompt_content(
            item_id,
            step_id,
            cycle_number,
            findings,
            max_cycles,
            gate_command,
            design_doc_block=design_doc_block,
        )
    elif step.step_type == StepType.browser_verification:
        prompt = _build_browser_fix_prompt_content(
            item_id,
            step_id,
            cycle_number,
            findings,
            max_cycles,
            prior_failure_reason=prior_failure_reason,
            design_doc_block=design_doc_block,
        )
    else:
        prompt = _build_fix_prompt_content(
            item_id,
            step_id,
            cycle_number,
            findings,
            max_cycles,
            design_doc_block=design_doc_block,
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
    *,
    design_doc_block: str = "",
) -> str:
    """Build a fix prompt for a quality validation failure."""
    escalation = ""
    if cycle_number == max_cycles:
        escalation = (
            f"\n\n**ESCALATION**: This is the FINAL fix cycle ({cycle_number}/{max_cycles}). "
            "**PREFER honest escalation over a Hail-Mary fix that drifts from the design "
            "spec.** If you cannot resolve every issue while staying aligned with the "
            "design doc, document which issues remain and why — the human reviewer can "
            "act on the evidence."
        )

    command_hint = ""
    if gate_command:
        command_hint = (
            f"\n\n## Gate Command\n\n"
            f"The quality gate that failed runs:\n```bash\n{gate_command}\n```\n\n"
            f"After applying fixes, re-run this command to verify the issues are resolved.\n"
        )

    design_section = f"{design_doc_block}\n" if design_doc_block else ""

    return (
        f"# {item_id} {step_id} QV Fix Cycle {cycle_number}/{max_cycles}\n\n"
        f"Quality gate {step_id} for work item {item_id} failed. "
        f"Fix the issues below so the gate passes on re-run.\n\n"
        f"{design_section}"
        f"## Diagnostic Hypothesis — Errors to Address\n\n"
        f"The block below is **one hypothesis** generated from the failed gate. "
        f"Verify it against the design doc spec above before applying any fix; "
        f"the spec wins on conflict.\n\n"
        f"{findings}\n"
        f"{command_hint}\n"
        f"## Pre-fix Procedure\n\n"
        f"1. **Read the design doc** at the path above. Skim the section that "
        f"covers this step's scope; quote-of-the-doc lives in this prompt when "
        f"available.\n"
        f"2. **Diff your target file(s) against the spec** — list deviations "
        f"explicitly before editing.\n"
        f"3. **Apply the minimum patch** to align code with the spec; the "
        f"reported errors should resolve as a side effect of that alignment.\n"
        f"4. **If the errors disagree with the spec, the spec wins.** Note the "
        f"disagreement in your output rather than silently following the errors.\n\n"
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
    *,
    design_doc_block: str = "",
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
            f"({cycle_number}/{max_cycles}). **PREFER honest escalation over a "
            "Hail-Mary fix that drifts from the design spec.** If you cannot "
            "make every failing V pass while staying aligned with the design "
            "doc above, document which V's remain and why so the human "
            "reviewer can act on the evidence."
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

    design_section = f"{design_doc_block}\n" if design_doc_block else ""

    return (
        f"# {item_id} {step_id} Browser Verification Fix Cycle "
        f"{cycle_number}/{max_cycles}\n\n"
        f"The end-to-end browser verification for step {step_id} of work item "
        f"{item_id} failed. The qv-browser agent ran V1..V(n) against the "
        f"isolated E2E stack (dashboard + DB built from this worktree) and "
        f"reported code defects. Apply the minimum patch to make every failing "
        f"V pass; the daemon will rebuild the E2E stack and re-run the browser "
        f"checks.\n\n"
        f"{design_section}"
        f"## Diagnostic Hypothesis — Browser Verification Report\n\n"
        f"The report below is **one hypothesis** about what's broken. The "
        f"qv-browser agent's *Root Cause* and `file:line` callouts are useful "
        f"clues, but they are not the spec. Verify against the design doc above "
        f"before applying any fix; the spec wins on conflict.\n\n"
        f"{findings}\n"
        f"{env_suspicion_block}"
        f"\n## Pre-fix Procedure\n\n"
        f"1. **Read the design doc** at the path above. Look for a "
        f"`Detailed Fix Specification` section or any spec for `{step_id}` / "
        f"the implementation step that this V suite verifies.\n"
        f"2. **Diff the target template / route / fixture against the spec.** "
        f"List deviations explicitly before editing — missing attributes, "
        f"wrong selectors, dropped guards. Browser failures are very often "
        f"the *implementation* drifting from a spec the design doc already "
        f"got right.\n"
        f"3. **Apply the minimum patch** to align code with the spec; failing "
        f"V's should resolve as a side effect of that alignment.\n"
        f"4. **If the report's root-cause hypothesis disagrees with the spec, "
        f"the spec wins.** Note the disagreement in your output rather than "
        f"silently following the report.\n\n"
        f"## Where to look\n\n"
        f"1. The design doc above is authoritative for *what should be true*.\n"
        f"2. The Diagnostic Hypothesis above points at *what's currently false*; "
        f"`file:line` references and screenshots are corroborating evidence, "
        f"not gospel.\n"
        f"3. Screenshots are under "
        f"`ai-dev/active/{item_id}/evidences/post/` — open the ones named in "
        f"the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.\n"
        f"4. The failing Vs typically map to:\n"
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
    *,
    design_doc_block: str = "",
) -> str:
    """Build the fix prompt content."""
    escalation = ""
    if cycle_number == max_cycles:
        escalation = (
            f"\n\n**ESCALATION**: This is the FINAL fix cycle ({cycle_number}/{max_cycles}). "
            "**PREFER honest escalation over a Hail-Mary fix that drifts from the design "
            "spec.** If you cannot resolve every finding while staying aligned with the "
            "design doc, document which findings remain and why — the human reviewer "
            "can act on the evidence."
        )

    design_section = f"{design_doc_block}\n" if design_doc_block else ""

    return (
        f"# {item_id} {step_id} Fix Cycle {cycle_number}/{max_cycles}\n\n"
        f"The code review for step {step_id} of work item {item_id} found issues "
        f"that must be fixed.\n\n"
        f"{design_section}"
        f"## Diagnostic Hypothesis — Findings to Address\n\n"
        f"The findings below are **one hypothesis** generated by a reviewer agent. "
        f"Verify them against the design doc spec above before applying any fix; "
        f"the spec wins on conflict.\n\n"
        f"{findings}\n\n"
        f"## Pre-fix Procedure\n\n"
        f"1. **Read the design doc** at the path above. Skim the section that "
        f"covers this step's scope.\n"
        f"2. **Diff your target file(s) against the spec** — list deviations "
        f"explicitly before editing.\n"
        f"3. **Apply the minimum patch** to align code with the spec; the "
        f"reported findings should resolve as a side effect of that alignment.\n"
        f"4. **If the findings disagree with the spec, the spec wins.** Note "
        f"the disagreement in your output rather than silently following the "
        f"findings.\n\n"
        f"## Constraints\n\n"
        f"1. **Only fix the flagged issues.** Do not refactor unrelated code.\n"
        f"2. **Preserve existing behavior.** Fixes must not break working functionality.\n"
        f"3. **Follow project conventions.** Read `CLAUDE.md` for patterns.\n"
        f"4. **Run tests after every fix.** Ensure no regressions.\n"
        f"{escalation}\n\n"
        f"## Instructions\n\n"
        f"1. Walk through the Pre-fix Procedure above before editing any file\n"
        f"2. Apply the minimum changes needed to align code with the spec and "
        f"resolve each finding\n"
        f"3. Run tests to verify no regressions\n"
        f"4. Exit when done — the daemon will detect completion and re-run the review\n\n"
        f"**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. "
        f"Simply apply the fixes and exit. The orchestrator handles the rest.\n"
    )


# ---------------------------------------------------------------------------
# Internal: fix agent launch
# ---------------------------------------------------------------------------


def _build_fix_launch_argv(cli_tool: str, inner_command: str) -> list[str]:
    """Build the argv (list form) for launching a fix agent.

    ``inner_command`` is a complete shell command — e.g.
    ``timeout 600 opencode run "$(cat /wt/.tmp/I-00074_S06_fix1.prompt)" --model x/y …``
    — that embeds a ``"$(cat …)"`` substitution and therefore double quotes.

    It MUST be passed as a single argv element so the *inner* shell parses it:

    * opencode behaves differently without a controlling TTY, so it is wrapped
      in ``script -qec <inner_command> /dev/null`` (``script`` runs the command
      via ``$SHELL -c``, allocating a PTY).
    * other CLIs run directly under ``/bin/sh -c <inner_command>``.

    Regression guard (I-00074): the previous implementation built
    ``f'script -qec "timeout … {command}" /dev/null'`` and ran it with
    ``shell=True``.  The ``"`` inside ``{command}`` (from ``"$(cat …)"``, added
    by F-00081) closed the wrapper's own ``-c`` quote, so the prompt text — any
    word starting with ``-``, e.g. ``-->`` from an embedded Mermaid snippet —
    leaked onto ``script``'s command line and it aborted with
    ``script: unrecognized option``.  Every opencode fix cycle failed silently.
    """
    if cli_tool == "opencode":
        return ["script", "-qec", inner_command, "/dev/null"]
    return ["/bin/sh", "-c", inner_command]


def _launch_fix_agent(
    db: Session,
    step: WorkflowStep,
    worktree_path: str,
    prompt_path: Path | None,
    project_config: ProjectConfig,
    config: DaemonConfig,  # noqa: ARG001
    cycle_number: int,
) -> tuple[int, Path, int, StepRun]:
    """Launch the fix agent subprocess.

    Returns (pid, log_file, timeout_secs, step_run).
    The step_run row is already committed so fix-cycle monitoring can track it.
    """
    from orch.agent_runtime.resolver import resolve_runtime  # noqa: PLC0415
    from orch.daemon.batch_manager import (  # noqa: PLC0415
        _build_agent_env,
        write_agent_prompt,
    )
    from orch.daemon.step_monitor import get_timeout  # noqa: PLC0415

    # F-00081: Resolve runtime option via cascade (step → item → project → catalogue default).
    work_item = (
        db.query(WorkItem).filter_by(project_id=project_config.id, id=step.work_item_id).first()
    )
    runtime_option = resolve_runtime(
        db,
        step=step,
        item=work_item,
        project=project_config,
    )
    resolved_cli_tool = runtime_option.cli_tool
    resolved_model = runtime_option.model

    item_id = step.work_item_id
    step_id = step.step_id
    fix_step_type = _FIX_TIMEOUT_MAP.get(step.step_type, "code_review_fix")
    timeout = get_timeout(project_config, fix_step_type)

    # Build the agent command with --model injected.  NOTE: this mirrors the
    # step launcher in ``batch_manager._launch_step`` — keep the two in sync.
    # (F-00081 updated the step launcher's `opencode run "$(cat …)"` form here
    # but left the `script -qec` wrapper below unescaped, which broke every
    # opencode fix cycle — see ``_build_fix_launch_argv``.)
    if prompt_path and prompt_path.exists():
        prompt_text = prompt_path.read_text()
    else:
        prompt_text = "Fix the code review findings."
    tmp_prompt = Path(worktree_path) / ".tmp" / f"{item_id}_{step_id}_fix{cycle_number}.prompt"
    tmp_prompt.parent.mkdir(parents=True, exist_ok=True)
    # I-00074: cap the prompt so a bloated fix-cycle prompt can't blow past
    # execve's per-argument limit when it's spliced in as `"$(cat …)"` below.
    write_agent_prompt(tmp_prompt, prompt_text)
    if resolved_cli_tool == "opencode":
        command = (
            f'opencode run "$(cat {tmp_prompt})" --model {resolved_model} '
            f"--dangerously-skip-permissions"
        )
    else:
        command = (
            f'claude -p "$(cat {tmp_prompt})" --model {resolved_model} '
            f"--dangerously-skip-permissions"
        )

    # Log file
    log_dir = Path(worktree_path) / "ai-dev" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{item_id}_{step_id}_fix{cycle_number}.log"

    # Build environment with belt-and-suspenders model env vars
    env = _build_agent_env(resolved_cli_tool, item_id, worktree_path)
    env["OPENCODE_MODEL"] = resolved_model
    env["ANTHROPIC_MODEL"] = resolved_model

    # Launch.  Pass argv as a list so the agent command (which embeds a
    # `"$(cat …)"` substitution) is handed to ``script``/``sh`` as one element
    # and parsed by the *inner* shell — never folded into an outer quoted
    # string. See ``_build_fix_launch_argv``.
    launch_argv = _build_fix_launch_argv(resolved_cli_tool, f"timeout {timeout} {command}")
    proc = subprocess.Popen(  # noqa: S603
        launch_argv,
        cwd=worktree_path,
        stdin=subprocess.DEVNULL,
        stdout=Path(log_file).open("w"),  # noqa: SIM115
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )

    logger.info(
        "Fix agent launched: %s/%s cycle %d (PID %d, timeout %ds, option_id=%d)",
        item_id,
        step_id,
        cycle_number,
        proc.pid,
        timeout,
        runtime_option.id,
    )

    # Persist step_runs row with agent_runtime_option_id
    now = datetime.now(UTC)
    run_number = _next_run_number(db, step)
    step_run = StepRun(
        step_id=step.id,
        run_number=run_number,
        status=RunStatus.running,
        pid=proc.pid,
        pid_alive=True,
        command=command,
        worktree_path=worktree_path,
        cli_tool=resolved_cli_tool,
        agent_runtime_option_id=runtime_option.id,
        log_file=str(log_file),
        started_at=now,
        last_heartbeat=now,
        timeout_secs=timeout,
    )
    db.add(step_run)
    db.commit()

    return proc.pid, log_file, timeout, step_run


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


def _files_changed_by_fix_cycle(cycle: FixCycle, worktree_path: str) -> list[str]:
    """Return list of file paths the fix cycle modified.

    Diffs cycle.fix_metadata['start_sha'] against the working tree
    (both committed AND uncommitted changes). Fix-cycle agents in this
    codebase leave files modified in the worktree without committing —
    so ``git diff <SHA>`` (no second arg) is used rather than
    ``git diff <SHA>..HEAD`` which would silently return empty when
    the agent left changes staged/unstaged but not committed.

    Returns [] when start_sha is missing, the diff command fails,
    or no files were changed.
    """
    meta = cycle.fix_metadata or {}
    start_sha = meta.get("start_sha")
    if not start_sha:
        return []
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "diff", "--name-only", start_sha],  # noqa: S607
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(
                "_files_changed_by_fix_cycle: git diff failed (exit %d): %s",
                result.returncode,
                result.stderr.strip(),
            )
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception as exc:  # noqa: BLE001
        logger.warning("_files_changed_by_fix_cycle: git diff error: %s", exc)
        return []


def _reset_review_steps_for_agents(
    db: Session,
    failing_step: WorkflowStep,
    agent_names: set[str],
    project_id: str,
) -> list[str]:
    """Reset every WorkflowStep whose layer matches agent_names AND step_type == code_review
    AND same work_item AND step_id < failing_step.step_id AND status == completed.

    Layer detection uses the prompt_file column: the filename convention is
    ``<item>_<step>_CodeReview_{Layer}_prompt.md``.  The layer keyword extracted
    from the filename (e.g. "Backend") is lower-cased and appended with "-review"
    to form a canonical agent name (e.g. "backend-review") for lookup in agent_names.

    Returns list of reset step_ids.
    """
    if not agent_names:
        return []

    candidates = (
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.work_item_id == failing_step.work_item_id,
            WorkflowStep.project_id == project_id,
            WorkflowStep.step_type == StepType.code_review,
            WorkflowStep.step_id < failing_step.step_id,
            WorkflowStep.status == StepStatus.completed,
        )
        .all()
    )

    reset_ids: list[str] = []
    for step in candidates:
        layer = _extract_review_layer(step)
        if layer and layer in agent_names:
            step.status = StepStatus.pending
            step.started_at = None
            step.completed_at = None
            reset_ids.append(step.step_id)

    return reset_ids


def _extract_review_layer(step: WorkflowStep) -> str | None:
    """Extract the normalised layer name from a code_review WorkflowStep.

    The prompt filename convention is ``<item>_<step>_CodeReview_{Layer}_prompt.md``.
    Returns e.g. ``"backend-review"`` for a file named
    ``CR-00036_S04_CodeReview_Backend_prompt.md``, or ``None`` when the
    prompt_file column is absent or the pattern doesn't match.
    """
    if not step.prompt_file:
        return None
    # Match the last component (basename) — prompt_file may be a relative path.
    basename = step.prompt_file.rsplit("/", 1)[-1]
    m = re.search(r"_CodeReview_([A-Za-z]+)_prompt\.md$", basename, re.IGNORECASE)
    if not m:
        return None
    layer_word = m.group(1).lower()  # e.g. "backend", "frontend", "api"
    return f"{layer_word}-review"


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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _next_run_number(db: Session, step: WorkflowStep) -> int:
    """Return the next run_number for a step (existing count + 1)."""
    count = db.query(StepRun).filter(StepRun.step_id == step.id).count()
    return count + 1
