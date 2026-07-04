"""Batch service functions for the orch platform.

Provides reusable, session-explicit functions that encapsulate all DB logic
for batch lifecycle operations. The same functions are called by the ``iw``
CLI and (in future) by the MCP server tool-handlers. Callers receive plain
dicts matching the existing CLI ``--json`` output shapes.

Re-exports :func:`orch.services.approve_merge` so MCP callers can import
everything batch-related from this module.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    WorkItemStatus,
    WorkItemType,
)

# Re-export for convenience — MCP callers import from orch.services.batches
from orch.services import approve_merge as approve_merge  # noqa: PLC0414
from orch.services._common import ServiceError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Active batch statuses (mirrors item_commands and batch_commands)
# ---------------------------------------------------------------------------

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
# create_batch
# ---------------------------------------------------------------------------


def create_batch(
    session: Session,
    project_id: str,
    item_ids: list[str],
    *,
    max_parallel: int = 4,
    auto_publish: bool = False,
    auto_merge: bool = True,
) -> dict[str, Any]:
    """Create a new batch from a list of approved work items.

    Allocates a batch ID via :func:`orch.cli.id_commands.allocate_next_id`,
    builds execution groups via topological sort, persists the Batch and
    BatchItem rows, then generates the execution plan diagram.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        item_ids: Ordered list of approved work-item identifiers.
        max_parallel: Maximum number of items to execute concurrently.
        auto_publish: When ``True``, auto-push to origin after all items merge.
        auto_merge: When ``True``, auto-merge each item to main on success.

    Returns:
        Dict matching CLI ``iw batch-create --json`` shape: ``batch_id``,
        ``project_id``, ``status``, ``max_parallel``, ``auto_merge``,
        ``auto_publish``, ``item_count``, ``groups``.

    Raises:
        ServiceError: When any item is not found, is a research item, is not
            approved, is already in an active batch, or a circular dependency
            is detected.
    """
    from orch.cli.batch_commands import build_execution_groups  # noqa: PLC0415
    from orch.cli.id_commands import allocate_next_id  # noqa: PLC0415

    # 1. Validate all items exist and are approved
    items = []
    for iid in item_ids:
        item = session.get(
            # local import avoids a circular import chain at module level
            __import__("orch.db.models", fromlist=["WorkItem"]).WorkItem,
            (project_id, iid),
        )
        if item is None:
            raise ServiceError(f"Work item {iid} not found in project {project_id}", code=1)
        if item.type == WorkItemType.Research:
            raise ServiceError(
                f"Work item {iid} is a research item and cannot be added to a batch — "
                "research items auto-complete via 'iw doc-update'",
                code=1,
            )
        if item.status != WorkItemStatus.approved:
            raise ServiceError(
                f"Work item {iid} is not approved (status: {item.status.value})",
                code=1,
            )
        items.append(item)

    # 2. Validate no item is already in an active batch
    for iid in item_ids:
        active = session.execute(
            select(BatchItem)
            .join(
                Batch,
                (BatchItem.project_id == Batch.project_id) & (BatchItem.batch_id == Batch.id),
            )
            .where(
                BatchItem.project_id == project_id,
                BatchItem.work_item_id == iid,
                Batch.status.in_(_ACTIVE_BATCH_STATUSES),
            )
        ).scalar_one_or_none()
        if active is not None:
            raise ServiceError(
                f"Work item {iid} is already in active batch {active.batch_id}",
                code=4,
            )

    # 3. Build execution groups
    item_deps: dict[str, list[str]] = {item.id: list(item.depends_on or []) for item in items}
    try:
        group_assignments = build_execution_groups(item_deps)
    except ValueError as exc:
        raise ServiceError(str(exc), code=1) from exc

    # 4. Allocate batch ID
    _num, batch_id = allocate_next_id(session, project_id, "BATCH")

    # 5. Create batch row
    batch = Batch(
        project_id=project_id,
        id=batch_id,
        status=BatchStatus.planning,
        max_parallel=max_parallel,
        auto_publish=auto_publish,
        auto_merge=auto_merge,
    )
    session.add(batch)
    session.flush()

    # 6. Create batch_items
    for iid in item_ids:
        session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=iid,
                execution_group=group_assignments[iid],
                status=BatchItemStatus.pending,
            )
        )
    session.flush()

    # 7. Generate execution plan (best-effort; imported lazily to avoid startup cost)
    try:
        from orch.cli.batch_commands import _generate_batch_plan  # noqa: PLC0415

        _generate_batch_plan(session, project_id, batch, items, group_assignments)
        session.flush()
    except Exception:  # noqa: BLE001
        # Plan generation is best-effort — a failure must not abort batch creation.
        logger.warning("Execution-plan generation failed for batch %s", batch_id, exc_info=True)

    # 8. Build groups summary
    groups_map: dict[int, list[str]] = {}
    for iid, grp in group_assignments.items():
        groups_map.setdefault(grp, []).append(iid)
    group_numbers = sorted(groups_map.keys())
    sorted_groups = [{"group": g, "items": groups_map[g]} for g in group_numbers]

    return {
        "batch_id": batch_id,
        "project_id": project_id,
        "status": "planning",
        "max_parallel": max_parallel,
        "auto_merge": auto_merge,
        "auto_publish": auto_publish,
        "item_count": len(item_ids),
        "groups": sorted_groups,
    }


# ---------------------------------------------------------------------------
# approve_batch
# ---------------------------------------------------------------------------


def approve_batch(session: Session, project_id: str, batch_id: str) -> dict[str, Any]:
    """Transition a batch from planning to approved.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        batch_id: Batch identifier.

    Returns:
        Dict with ``project_id``, ``batch_id``, ``status`` (``"approved"``).
        Matches CLI ``iw batch-approve --json``.

    Raises:
        ServiceError: When the batch is not found or is not in planning status.
    """
    from orch.cli.batch_commands import validate_batch_approve_transition  # noqa: PLC0415
    from orch.qv_gate_validator import auto_skip_phantom_qv_gates  # noqa: PLC0415

    batch = session.get(Batch, (project_id, batch_id))
    if batch is None:
        raise ServiceError(f"Batch {batch_id} not found in project {project_id}", code=1)

    error = validate_batch_approve_transition(batch.status)
    if error:
        raise ServiceError(error, code=1)

    batch.status = BatchStatus.approved
    batch.updated_at = datetime.now(UTC)
    session.flush()

    session.add(
        DaemonEvent(
            project_id=project_id,
            event_type="batch_approved",
            entity_id=batch_id,
            entity_type="batch",
            message=f"Batch {batch_id} approved for execution",
        )
    )
    session.flush()

    # Auto-skip phantom QV gates on all batch items
    batch_items = (
        session.query(BatchItem)
        .filter(BatchItem.project_id == project_id, BatchItem.batch_id == batch_id)
        .all()
    )
    all_skipped: list[tuple[str, str, str]] = []
    for bi in batch_items:
        skipped = auto_skip_phantom_qv_gates(
            session, project_id, bi.work_item_id, trigger="batch_approve"
        )
        all_skipped.extend(skipped)

    result: dict[str, Any] = {"project_id": project_id, "batch_id": batch_id, "status": "approved"}
    if all_skipped:
        result["auto_skipped_steps"] = [
            {"step_id": s, "gate": g, "reason": r} for s, g, r in all_skipped
        ]
    return result


# ---------------------------------------------------------------------------
# get_batch_status
# ---------------------------------------------------------------------------


def get_batch_status(session: Session, project_id: str, batch_id: str) -> dict[str, Any]:
    """Return the full status dict for a batch.

    The returned dict is byte-identical to the CLI ``iw batch-status --json``
    output shape.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        batch_id: Batch identifier.

    Returns:
        Dict with ``batch_id``, ``project_id``, ``status``, ``max_parallel``,
        ``auto_publish``, ``created_at``, and ``items`` (list of batch-item
        sub-dicts).

    Raises:
        ServiceError: When the batch is not found.
    """
    batch = session.get(Batch, (project_id, batch_id))
    if batch is None:
        raise ServiceError(f"Batch {batch_id} not found in project {project_id}", code=1)

    batch_items = (
        session.execute(
            select(BatchItem)
            .where(BatchItem.project_id == project_id, BatchItem.batch_id == batch_id)
            .order_by(BatchItem.execution_group, BatchItem.work_item_id)
        )
        .scalars()
        .all()
    )

    return {
        "batch_id": batch_id,
        "project_id": project_id,
        "status": batch.status.value,
        "max_parallel": batch.max_parallel,
        "auto_publish": batch.auto_publish,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "items": [
            {
                "work_item_id": bi.work_item_id,
                "execution_group": bi.execution_group,
                "status": bi.status.value,
                "started_at": bi.started_at.isoformat() if bi.started_at else None,
                "merged_at": bi.merged_at.isoformat() if bi.merged_at else None,
            }
            for bi in batch_items
        ],
    }


# ---------------------------------------------------------------------------
# pause_batch / resume_batch
# ---------------------------------------------------------------------------


def pause_batch(session: Session, project_id: str, batch_id: str) -> dict[str, Any]:
    """Transition a batch from executing to paused.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        batch_id: Batch identifier.

    Returns:
        Dict with ``project_id``, ``batch_id``, ``status`` (``"paused"``).
        Matches CLI ``iw batch-pause --json``.

    Raises:
        ServiceError: When the batch is not found or is not in executing status.
    """
    from orch.cli.batch_commands import validate_batch_pause_transition  # noqa: PLC0415

    batch = session.get(Batch, (project_id, batch_id))
    if batch is None:
        raise ServiceError(f"Batch {batch_id} not found in project {project_id}", code=1)

    error = validate_batch_pause_transition(batch.status)
    if error:
        raise ServiceError(error, code=1)

    batch.status = BatchStatus.paused
    batch.updated_at = datetime.now(UTC)
    session.flush()

    return {"project_id": project_id, "batch_id": batch_id, "status": "paused"}


def resume_batch(session: Session, project_id: str, batch_id: str) -> dict[str, Any]:
    """Transition a batch from paused to executing.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        batch_id: Batch identifier.

    Returns:
        Dict with ``project_id``, ``batch_id``, ``status`` (``"executing"``).
        Matches CLI ``iw batch-resume --json``.

    Raises:
        ServiceError: When the batch is not found or is not in paused status.
    """
    from orch.cli.batch_commands import validate_batch_resume_transition  # noqa: PLC0415

    batch = session.get(Batch, (project_id, batch_id))
    if batch is None:
        raise ServiceError(f"Batch {batch_id} not found in project {project_id}", code=1)

    error = validate_batch_resume_transition(batch.status)
    if error:
        raise ServiceError(error, code=1)

    batch.status = BatchStatus.executing
    batch.updated_at = datetime.now(UTC)
    session.flush()

    return {"project_id": project_id, "batch_id": batch_id, "status": "executing"}


# ---------------------------------------------------------------------------
# cancel_batch_service
# ---------------------------------------------------------------------------


def cancel_batch_service(
    session: Session,
    project_id: str,
    batch_id: str,
    *,
    reason: str = "cancelled by operator",
    reset_items: bool = False,
) -> dict[str, Any]:
    """Cancel a batch and all non-terminal items.

    Thin wrapper over :func:`orch.cancel.cancel_batch` that returns a plain
    dict matching the CLI ``iw batch-cancel --json`` shape.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        batch_id: Batch identifier.
        reason: Free-text reason recorded on the batch and each cancelled item.
        reset_items: When ``True``, reset work items to ``draft`` instead of
            ``cancelled``.

    Returns:
        Dict with ``project_id``, ``batch_id``, ``status`` (``"cancelled"``),
        ``reset_items``, ``cancelled_batch_items``, ``reset_to_draft``,
        ``killed_pids``, ``teardown_errors``.

    Raises:
        ServiceError: When the batch is not found or is not cancellable.
    """
    from orch.cancel import cancel_batch  # noqa: PLC0415

    try:
        cancel_result = cancel_batch(
            session, project_id, batch_id, reason=reason, reset_items=reset_items
        )
    except LookupError as exc:
        raise ServiceError(str(exc), code=1) from exc
    except ValueError as exc:
        raise ServiceError(str(exc), code=1) from exc

    return {
        "project_id": project_id,
        "batch_id": batch_id,
        "status": "cancelled",
        "reset_items": reset_items,
        "cancelled_batch_items": cancel_result.cancelled_batch_items,
        "reset_to_draft": cancel_result.reset_to_draft,
        "killed_pids": cancel_result.killed_pids,
        "teardown_errors": cancel_result.teardown_errors,
    }


# ---------------------------------------------------------------------------
# list_batches
# ---------------------------------------------------------------------------


def list_batches(
    session: Session,
    project_id: str,
    *,
    status: str | None = None,
) -> dict[str, Any]:
    """Return a list of batches for a project, ordered newest-first.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        status: Optional status filter (e.g. ``"planning"``, ``"approved"``).

    Returns:
        Dict with key ``batches``: a list of batch summary dicts each
        containing ``batch_id``, ``status``, ``item_count``,
        ``completed_count``, ``created_at``.
    """
    stmt = select(Batch).where(Batch.project_id == project_id).order_by(Batch.created_at.desc())

    if status:
        try:
            stmt = stmt.where(Batch.status == BatchStatus(status))
        except ValueError:
            # Unknown status → return empty
            return {"batches": []}

    batches = list(session.scalars(stmt).all())

    result_batches: list[dict[str, Any]] = []
    for batch in batches:
        items = list(
            session.scalars(
                select(BatchItem).where(
                    BatchItem.project_id == project_id,
                    BatchItem.batch_id == batch.id,
                )
            ).all()
        )
        total_items = len(items)
        completed_items = sum(1 for it in items if it.status.value in ("completed", "merged"))

        result_batches.append(
            {
                "batch_id": batch.id,
                "status": batch.status.value,
                "item_count": total_items,
                "completed_count": completed_items,
                "created_at": batch.created_at.isoformat() if batch.created_at else None,
            }
        )

    return {"batches": result_batches}
