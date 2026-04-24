"""Shared batch-progress computation helper — single source of truth for progress_pct."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import case, func, select

from orch.db.models import BatchItem, StepStatus, WorkflowStep

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.orm import Session


def compute_batch_step_progress(
    project_id: str,
    batch_ids: Sequence[str],
    db: Session,
) -> dict[str, int]:
    """
    Return {batch_id: progress_pct} for each requested batch.

    progress_pct = round(done_steps / total_steps * 100) as an int in [0, 100],
    where:
      - total_steps = count of WorkflowStep rows for all work items
        referenced by BatchItems of the batch, scoped to project_id.
      - done_steps  = count of those WorkflowStep rows with status in
        {StepStatus.completed, StepStatus.skipped}.

    Batches with no steps (empty batch, or items with no WorkflowStep rows yet)
    map to 0. Any requested batch_id not present in the DB also maps to 0 —
    the caller can iterate its own batch list and index into the dict without
    handling KeyError.
    """
    if not batch_ids:
        return {}

    stmt = (
        select(
            BatchItem.batch_id,
            func.count(WorkflowStep.id).label("total"),
            func.sum(
                case(
                    (
                        WorkflowStep.status.in_([StepStatus.completed, StepStatus.skipped]),
                        1,
                    ),
                    else_=0,
                )
            ).label("done"),
        )
        .join(
            WorkflowStep,
            (WorkflowStep.project_id == BatchItem.project_id)
            & (WorkflowStep.work_item_id == BatchItem.work_item_id),
        )
        .where(
            BatchItem.project_id == project_id,
            BatchItem.batch_id.in_(batch_ids),
        )
        .group_by(BatchItem.batch_id)
    )

    result: dict[str, int] = dict.fromkeys(batch_ids, 0)
    for row in db.execute(stmt).all():
        total = row.total or 0
        done = row.done or 0
        pct = int((done / total * 100) if total > 0 else 0)
        result[row.batch_id] = pct

    return result
