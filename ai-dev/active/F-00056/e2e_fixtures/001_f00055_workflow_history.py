"""E2E fixture: seed F-00055's workflow history so the execution-report tab
renders the real retry hotspots during F-00056's browser verification.

Without this, the E2E DB has F-00055 as a completed WorkItem but with zero
``step_runs`` / ``fix_cycles`` rows. The execution-report tab correctly
renders "No retries — clean run." and V1/V2/V3 fail even though F-00056's
implementation is correct.

The step counts and durations below are copied verbatim from
``ai-dev/archive/F-00055/F-00055_execution_report.md``:

    S01 Pipeline            × 1 (6m 32s)      S10 CodeReview       × 2 (5m 29s)
    S02 CodeReview          × 1 (1m 0s)       S11 CodeReviewFinal  × 2 (23m 3s)
    S03 Backend             × 1 (20m 53s)     S12 CodeReviewFixFinal× 1 (16m 4s)
    S04 CodeReview          × 1 (1m 40s)      S13 QvGate           × 3 (18m 48s)
    S05 Api                 × 1 (12m 15s)     S14 QvGate           × 1 (12s)
    S06 CodeReview          × 1 (50s)         S15 QvGate           × 1 (12s)
    S07 Frontend            × 1 (2m 45s)      S16 QvGate           × 2 (24m 46s)
    S08 CodeReview          × 1 (1m 10s)      S17 QvGate           × 1 (1m 31s)
    S09 Tests               × 1 (29m 0s)      S18 QvBrowser        × 6 (2h 53m)

Fix cycles (trigger_type, cycle_number, duration_secs):
    S11: code_review_final × 1 (420s)
    S13: quality_validation × 2 (120s, 780s)
    S16: quality_validation × 1 (1320s)
    S18: browser_verification × 2 (540s, 240s)

Idempotent: guards on WorkflowStep existence so re-seeding is a no-op.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from orch.db.models import (
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

PROJECT_ID = "iw-ai-core"
ITEM_ID = "F-00055"
ITEM_STARTED_AT = datetime(2026, 4, 19, 21, 14, 37, tzinfo=UTC)

# (step_number, step_id, agent_label, step_type, attempts, duration_secs)
_STEPS: list[tuple[int, str, str, StepType, int, int]] = [
    (1, "S01", "Pipeline", StepType.implementation, 1, 392),
    (2, "S02", "CodeReview", StepType.code_review, 1, 60),
    (3, "S03", "Backend", StepType.implementation, 1, 1253),
    (4, "S04", "CodeReview", StepType.code_review, 1, 100),
    (5, "S05", "Api", StepType.implementation, 1, 735),
    (6, "S06", "CodeReview", StepType.code_review, 1, 50),
    (7, "S07", "Frontend", StepType.implementation, 1, 165),
    (8, "S08", "CodeReview", StepType.code_review, 1, 70),
    (9, "S09", "Tests", StepType.implementation, 1, 1740),
    (10, "S10", "CodeReview", StepType.code_review, 2, 329),
    (11, "S11", "CodeReviewFinal", StepType.code_review_final, 2, 1383),
    (12, "S12", "CodeReviewFixFinal", StepType.code_review_fix_final, 1, 964),
    (13, "S13", "QvGate", StepType.quality_validation, 3, 1128),
    (14, "S14", "QvGate", StepType.quality_validation, 1, 12),
    (15, "S15", "QvGate", StepType.quality_validation, 1, 12),
    (16, "S16", "QvGate", StepType.quality_validation, 2, 1486),
    (17, "S17", "QvGate", StepType.quality_validation, 1, 91),
    (18, "S18", "QvBrowser", StepType.browser_verification, 6, 10380),
]

# (step_id, trigger_type, [cycle_durations_secs])
_FIX_CYCLES: list[tuple[str, FixTrigger, list[int]]] = [
    ("S11", FixTrigger.code_review_final, [420]),
    ("S13", FixTrigger.quality_validation, [120, 780]),
    ("S16", FixTrigger.quality_validation, [1320]),
    ("S18", FixTrigger.browser_verification, [540, 240]),
]


def _existing_step(db: Session, step_id: str) -> WorkflowStep | None:
    return db.execute(
        select(WorkflowStep).where(
            WorkflowStep.project_id == PROJECT_ID,
            WorkflowStep.work_item_id == ITEM_ID,
            WorkflowStep.step_id == step_id,
        )
    ).scalar_one_or_none()


def seed(db: Session) -> None:
    cursor = ITEM_STARTED_AT
    step_record_by_id: dict[str, WorkflowStep] = {}

    for step_number, step_id, agent_label, step_type, attempts, dur_secs in _STEPS:
        step_started = cursor
        step_completed = cursor + timedelta(seconds=dur_secs)
        cursor = step_completed

        existing = _existing_step(db, step_id)
        if existing is not None:
            step_record_by_id[step_id] = existing
            continue

        step = WorkflowStep(
            project_id=PROJECT_ID,
            work_item_id=ITEM_ID,
            step_number=step_number,
            step_id=step_id,
            agent_label=agent_label,
            step_type=step_type,
            step_label=agent_label,
            status=StepStatus.completed,
            started_at=step_started,
            completed_at=step_completed,
        )
        db.add(step)
        db.flush()
        step_record_by_id[step_id] = step

        # Distribute attempts evenly across the step's window. The last run
        # is the "final" completed attempt; any prior runs are retries.
        slice_secs = dur_secs / attempts
        for run_number in range(1, attempts + 1):
            run_started = step_started + timedelta(seconds=slice_secs * (run_number - 1))
            run_completed = step_started + timedelta(seconds=slice_secs * run_number)
            is_final = run_number == attempts
            db.add(
                StepRun(
                    step_id=step.id,
                    run_number=run_number,
                    status=RunStatus.completed if is_final else RunStatus.failed,
                    started_at=run_started,
                    completed_at=run_completed,
                    duration_secs=float(slice_secs),
                    error_message=None if is_final else f"retry {run_number} of {attempts}",
                )
            )
        db.flush()

    # Fix cycles — placed between the run windows so the Gantt timeline shows them.
    for step_id, trigger, cycle_durations in _FIX_CYCLES:
        step = step_record_by_id.get(step_id)
        if step is None:
            continue
        anchor = step.started_at or ITEM_STARTED_AT
        existing_cycles = (
            db.execute(select(FixCycle).where(FixCycle.step_id == step.id)).scalars().all()
        )
        if existing_cycles:
            continue
        cursor_c = anchor + timedelta(seconds=60)
        for idx, dur_secs in enumerate(cycle_durations, start=1):
            db.add(
                FixCycle(
                    step_id=step.id,
                    cycle_number=idx,
                    trigger_type=trigger,
                    status=FixStatus.completed,
                    started_at=cursor_c,
                    completed_at=cursor_c + timedelta(seconds=dur_secs),
                    fix_metadata={},
                    # fix_summary left NULL → template renders the
                    # "no fix summary captured (pre-F-00056)" placeholder
                )
            )
            cursor_c += timedelta(seconds=dur_secs + 30)
        db.flush()
