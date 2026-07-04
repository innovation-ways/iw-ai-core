"""Monitoring service functions for the orch platform.

Provides a unified view over all background job tables via
:class:`orch.jobs.aggregator.JobsAggregator`, project listing, active worktree
enumeration, and daemon DB statistics. Returns plain dicts suitable for both
CLI consumption and MCP tool responses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.orm import Session


def list_jobs(
    session: Session,
    project_id: str,
    *,
    types: list[str] | None = None,
    statuses: list[str] | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    """Return a paginated list of jobs from all sources for a project.

    Wraps :class:`orch.jobs.aggregator.JobsAggregator` and serialises the
    result to plain dicts so callers never touch ORM objects.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project to query.
        types: Optional list of job-type strings to restrict results.  Valid
            values match :class:`orch.jobs.aggregator.JobType` members
            (e.g. ``"batch_execution"``, ``"doc_generation"``).
        statuses: Optional list of normalised status strings to filter on
            (e.g. ``"queued"``, ``"running"``, ``"completed"``).
        page: 1-based page number.
        page_size: Number of rows per page.

    Returns:
        Dict with keys:

        - ``jobs``: list of job dicts, each with ``job_type``, ``job_id``,
          ``project_id``, ``title``, ``status``, ``started_at``,
          ``finished_at``, ``triggered_by``.
        - ``total``: total matching rows before pagination.
        - ``page``: current page number.
        - ``page_size``: rows per page.
    """
    import contextlib  # noqa: PLC0415

    from orch.jobs.aggregator import JobsAggregator, JobType  # noqa: PLC0415

    # Convert string type names to JobType enum members; unknown names are
    # skipped (job_list is a lenient monitoring filter, not a strict lookup).
    job_types: list[JobType] | None = None
    if types is not None:
        resolved: list[JobType] = []
        for t in types:
            with contextlib.suppress(ValueError):
                resolved.append(JobType(t))
        job_types = resolved if resolved else None

    aggregator = JobsAggregator(session)
    result = aggregator.list_jobs(
        project_id=project_id,
        types=job_types,
        statuses=statuses,
        page=page,
        page_size=page_size,
    )

    def _dt_or_none(dt: datetime | None) -> str | None:
        """Serialise a datetime to ISO-8601 string or return None."""
        if dt is None:
            return None
        return str(dt.isoformat())

    jobs = [
        {
            "job_type": row.job_type.value,
            "job_id": row.job_id,
            "project_id": row.project_id,
            "title": row.title,
            "status": row.status,
            "started_at": _dt_or_none(row.started_at),
            "finished_at": _dt_or_none(row.finished_at),
            "triggered_by": row.triggered_by,
        }
        for row in result.rows
    ]

    return {
        "jobs": jobs,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
    }


def list_projects(session: Session) -> dict[str, Any]:
    """Return all registered projects ordered by id.

    Args:
        session: Active SQLAlchemy session.

    Returns:
        Dict with key ``projects``: a list of project dicts each containing
        ``id``, ``display_name``, ``enabled``, and ``repo_root``.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from orch.db.models import Project  # noqa: PLC0415

    rows = list(session.scalars(select(Project).order_by(Project.id)).all())
    return {
        "projects": [
            {
                "id": r.id,
                "display_name": r.display_name,
                "enabled": r.enabled,
                "repo_root": r.repo_root,
            }
            for r in rows
        ]
    }


def list_worktrees(session: Session, project_id: str) -> dict[str, Any]:
    """Return active worktree rows for a project.

    Queries ``BatchItem`` rows for the project that have a non-null
    ``worktree_info`` JSON field or a ``started_at`` without a ``merged_at``
    (i.e. still executing).  No git subprocess is invoked — the result is
    DB-only.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project to query.

    Returns:
        Dict with key ``worktrees``: a list of dicts each containing
        ``work_item_id``, ``batch_id``, ``execution_group``,
        ``worktree_info``, and ``started_at`` (ISO-8601 string or ``None``).
    """
    from sqlalchemy import or_, select  # noqa: PLC0415

    from orch.db.models import BatchItem  # noqa: PLC0415

    stmt = (
        select(BatchItem)
        .where(
            BatchItem.project_id == project_id,
            or_(
                BatchItem.worktree_info.is_not(None),
                # Non-null started_at without a merged_at = still in flight
                (BatchItem.started_at.is_not(None) & BatchItem.merged_at.is_(None)),
            ),
        )
        .order_by(BatchItem.started_at.desc())
    )
    rows = list(session.scalars(stmt).all())
    return {
        "worktrees": [
            {
                "work_item_id": r.work_item_id,
                "batch_id": r.batch_id,
                "execution_group": r.execution_group,
                "worktree_info": r.worktree_info,
                "started_at": r.started_at.isoformat() if r.started_at else None,
            }
            for r in rows
        ]
    }


def get_daemon_db_stats(session: Session) -> dict[str, Any]:
    """Return the DB-portion of daemon status (mirrors ``iw daemon status``).

    Replicates the database queries performed by the ``daemon status``
    CLI subcommand without checking OS-level process liveness (PID file
    checks are the caller's responsibility).

    Args:
        session: Active SQLAlchemy session.

    Returns:
        Dict with keys ``last_poll_at`` (ISO-8601 or ``None``),
        ``poll_count``, ``running_steps``, ``active_batches``, and
        ``projects`` (``{"enabled": int, "disabled": int}``).
    """
    from sqlalchemy import func, select  # noqa: PLC0415

    from orch.db.models import (  # noqa: PLC0415
        Batch,
        BatchStatus,
        DaemonEvent,
        Project,
        StepStatus,
        WorkflowStep,
    )

    _active_batch_statuses = [BatchStatus.executing, BatchStatus.publishing]

    last_poll = session.execute(
        select(DaemonEvent)
        .where(DaemonEvent.event_type == "daemon_poll")
        .order_by(DaemonEvent.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    poll_count = session.execute(
        select(func.count(DaemonEvent.id)).where(DaemonEvent.event_type == "daemon_poll")
    ).scalar_one()

    running_steps = session.execute(
        select(func.count(WorkflowStep.id)).where(WorkflowStep.status == StepStatus.in_progress)
    ).scalar_one()

    active_batches = session.execute(
        select(func.count()).select_from(Batch).where(Batch.status.in_(_active_batch_statuses))
    ).scalar_one()

    enabled_projects = session.execute(
        select(func.count(Project.id)).where(Project.enabled.is_(True))
    ).scalar_one()

    disabled_projects = session.execute(
        select(func.count(Project.id)).where(Project.enabled.is_(False))
    ).scalar_one()

    return {
        "last_poll_at": last_poll.created_at.isoformat() if last_poll else None,
        "poll_count": poll_count,
        "running_steps": running_steps,
        "active_batches": active_batches,
        "projects": {"enabled": enabled_projects, "disabled": disabled_projects},
    }
