"""Integration tests for item view step Duration aggregation (I-00034).

Tests verify that step Duration spans from the first attempt's started_at
through the last completion across step_runs and fix_cycles — NOT just
the last iteration's WorkflowStep.started_at/completed_at.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import event

from dashboard.routers.items import _get_metrics, _get_steps
from orch.db.models import (
    FixCycle,
    FixStatus,
    FixTrigger,
    Project,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def make_step_run(
    db: Session,
    step_id: int,
    run_number: int,
    status: RunStatus,
    started_at: datetime,
    completed_at: datetime | None,
) -> StepRun:
    """Create and flush a StepRun row for the given step.

    Args:
        db: SQLAlchemy session to use for the insert.
        step_id: Primary key of the parent WorkflowStep.
        run_number: Sequential run attempt number (1-based).
        status: Execution status of this run attempt.
        started_at: Timestamp when this run attempt began.
        completed_at: Timestamp when this run attempt ended, or None if still running.

    Returns:
        The newly flushed StepRun instance.
    """
    run = StepRun(
        step_id=step_id,
        run_number=run_number,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
    )
    db.add(run)
    db.flush()
    return run


def make_fix_cycle(
    db: Session,
    step_id: int,
    cycle_number: int,
    status: FixStatus,
    started_at: datetime,
    completed_at: datetime | None,
) -> FixCycle:
    """Create and flush a FixCycle row for the given step.

    Args:
        db: SQLAlchemy session to use for the insert.
        step_id: Primary key of the parent WorkflowStep.
        cycle_number: Sequential fix-cycle number (1-based).
        status: Completion status of this fix cycle.
        started_at: Timestamp when this fix cycle began.
        completed_at: Timestamp when this fix cycle ended, or None if still running.

    Returns:
        The newly flushed FixCycle instance.
    """
    cycle = FixCycle(
        step_id=step_id,
        cycle_number=cycle_number,
        trigger_type=FixTrigger.code_review,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
    )
    db.add(cycle)
    db.flush()
    return cycle


def _make_work_item(
    db: Session,
    project_id: str,
    item_id: str,
) -> WorkItem:
    """Create and flush a minimal WorkItem row for duration aggregation tests.

    Args:
        db: SQLAlchemy session to use for the insert.
        project_id: ID of the owning project.
        item_id: Human-readable work item identifier (e.g. "I-00034").

    Returns:
        The newly flushed WorkItem instance.
    """
    work_item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Issue,
        title="Duration Bug Test Item",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(work_item)
    db.flush()
    return work_item


class TestI00034StepDurationAggregation:
    """I-00034: per-step duration must span first attempt to last completion."""

    def test_I00034_step_duration_spans_first_run_to_last_completion(  # noqa: N802
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Reproducing test: duration MUST be 630s (10m30s), not 30s.

        Fixture:
          run#1:  12:00:00 -> 12:02:00  (failed,  2 min)
          cycle#1: 12:03:00 -> 12:09:00  (completed, 6 min)
          run#2:  12:10:00 -> 12:10:30  (success, 30 sec)

        Full span: 12:00:00 -> 12:10:30 = 10m 30s = 630 seconds.
        The buggy code reads WorkflowStep.started_at/completed_at which are
        reset to the LAST iteration values (12:10:00 / 12:10:30), returning 30s.
        """
        project = test_project
        item_id = "I-00034"
        _make_work_item(db_session, project.id, item_id)

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.completed,
            started_at=datetime(2026, 4, 22, 12, 10, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 12, 10, 30, tzinfo=UTC),
        )
        db_session.add(step)
        db_session.flush()

        make_step_run(
            db_session,
            step_id=step.id,
            run_number=1,
            status=RunStatus.failed,
            started_at=datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 12, 2, 0, tzinfo=UTC),
        )
        make_fix_cycle(
            db_session,
            step_id=step.id,
            cycle_number=1,
            status=FixStatus.completed,
            started_at=datetime(2026, 4, 22, 12, 3, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 12, 9, 0, tzinfo=UTC),
        )
        make_step_run(
            db_session,
            step_id=step.id,
            run_number=2,
            status=RunStatus.completed,
            started_at=datetime(2026, 4, 22, 12, 10, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 12, 10, 30, tzinfo=UTC),
        )

        steps = _get_steps(project.id, item_id, db_session)

        real_step = next(s for s in steps if s.step_id == "S01")
        assert real_step.duration_secs == pytest.approx(630)
        assert real_step.started_at == datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)
        assert real_step.completed_at == datetime(2026, 4, 22, 12, 10, 30, tzinfo=UTC)

    def test_I00034_total_duration_spans_full_item(  # noqa: N802
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Total Time card must span the full aggregated item window, not just last iteration."""
        project = test_project
        item_id = "I-00034"
        _make_work_item(db_session, project.id, item_id)

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.completed,
            started_at=datetime(2026, 4, 22, 12, 10, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 12, 10, 30, tzinfo=UTC),
        )
        db_session.add(step)
        db_session.flush()

        make_step_run(
            db_session,
            step_id=step.id,
            run_number=1,
            status=RunStatus.failed,
            started_at=datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 12, 2, 0, tzinfo=UTC),
        )
        make_fix_cycle(
            db_session,
            step_id=step.id,
            cycle_number=1,
            status=FixStatus.completed,
            started_at=datetime(2026, 4, 22, 12, 3, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 12, 9, 0, tzinfo=UTC),
        )
        make_step_run(
            db_session,
            step_id=step.id,
            run_number=2,
            status=RunStatus.completed,
            started_at=datetime(2026, 4, 22, 12, 10, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 12, 10, 30, tzinfo=UTC),
        )

        steps = _get_steps(project.id, item_id, db_session)
        metrics = _get_metrics(project.id, item_id, steps, db_session)

        assert metrics.total_duration_secs == pytest.approx(630)

    def test_I00034_happy_path_single_run_duration_unchanged(  # noqa: N802
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Single-run steps must still show the correct 45s duration (regression guard)."""
        project = test_project
        item_id = "I-00034"
        _make_work_item(db_session, project.id, item_id)

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.completed,
            started_at=datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 12, 0, 45, tzinfo=UTC),
        )
        db_session.add(step)
        db_session.flush()

        make_step_run(
            db_session,
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 12, 0, 45, tzinfo=UTC),
        )

        steps = _get_steps(project.id, item_id, db_session)
        real_step = next(s for s in steps if s.step_id == "S01")

        assert real_step.duration_secs == pytest.approx(45)
        assert real_step.started_at == datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)
        assert real_step.completed_at == datetime(2026, 4, 22, 12, 0, 45, tzinfo=UTC)

    def test_I00034_in_progress_step_returns_none_duration_and_aggregated_start(  # noqa: N802
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """In-progress steps: duration is None (template renders '—'), but started_at is earliest.

        NOTE: S01's _aggregate_step_spans uses SQL MAX() which ignores NULLs.
        A step with one completed run and one running run (completed_at=NULL)
        returns MAX=T0 (the completed run's value), not None. This is a pre-existing
        S01 bug. The correct behavior (per AC3) is duration=None for in-progress.
        This test asserts the EXPECTED correct behavior, documenting the gap.
        """
        project = test_project
        item_id = "I-00034"
        _make_work_item(db_session, project.id, item_id)

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.in_progress,
            started_at=None,
            completed_at=None,
        )
        db_session.add(step)
        db_session.flush()

        t0 = datetime(2026, 4, 22, 13, 0, 0, tzinfo=UTC)
        make_step_run(
            db_session,
            step_id=step.id,
            run_number=1,
            status=RunStatus.failed,
            started_at=t0,
            completed_at=t0,
        )
        make_step_run(
            db_session,
            step_id=step.id,
            run_number=2,
            status=RunStatus.running,
            started_at=t0,
            completed_at=None,
        )

        steps = _get_steps(project.id, item_id, db_session)
        real_step = next(s for s in steps if s.step_id == "S01")

        assert real_step.started_at == t0
        # AC3: duration must be None for in-progress so template renders "—"
        # NOTE: This currently fails against S01 due to SQL MAX() ignoring NULLs.
        # The correct fix is to detect NULL completed_at in aggregation and return None.
        assert real_step.duration_secs is None, (
            f"Expected None for in-progress step (one run has NULL completed_at), "
            f"got {real_step.duration_secs} — SQL MAX() ignores NULLs, S01 bug"
        )

    def test_I00034_mixed_tables_incomplete_fix_cycle_yields_none_latest(  # noqa: N802
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Regression: step with completed run + in-progress fix_cycle must not raise.

        Reproduces the TypeError in _aggregate_step_spans that 500'd
        /project/{id}/item/{item_id} when existing[1] was a datetime (from
        step_runs aggregate) and row.latest was None (fix_cycles CASE returned
        NULL because at least one cycle was still running). The previous guard
        only nulled the merged latest when BOTH sides were None, so max() was
        called with (datetime, None) and blew up.
        """
        project = test_project
        item_id = "I-00034"
        _make_work_item(db_session, project.id, item_id)

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.in_progress,
            started_at=None,
            completed_at=None,
        )
        db_session.add(step)
        db_session.flush()

        t0 = datetime(2026, 4, 22, 14, 0, 0, tzinfo=UTC)
        t1 = datetime(2026, 4, 22, 14, 1, 0, tzinfo=UTC)
        t2 = datetime(2026, 4, 22, 14, 2, 0, tzinfo=UTC)
        make_step_run(
            db_session,
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=t0,
            completed_at=t1,
        )
        make_fix_cycle(
            db_session,
            step_id=step.id,
            cycle_number=1,
            status=FixStatus.in_progress,
            started_at=t2,
            completed_at=None,
        )

        steps = _get_steps(project.id, item_id, db_session)
        real_step = next(s for s in steps if s.step_id == "S01")

        assert real_step.started_at == t0
        assert real_step.completed_at is None
        assert real_step.duration_secs is None

    def test_I00034_never_launched_step_duration_is_none(  # noqa: N802
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Pending steps with zero runs/cycles must have None duration and None started_at."""
        project = test_project
        item_id = "I-00034"
        _make_work_item(db_session, project.id, item_id)

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.pending,
            started_at=None,
            completed_at=None,
        )
        db_session.add(step)
        db_session.flush()

        steps = _get_steps(project.id, item_id, db_session)
        real_step = next(s for s in steps if s.step_id == "S01")

        assert real_step.duration_secs is None
        assert real_step.started_at is None
        assert real_step.completed_at is None

    def test_I00034_get_steps_query_count_is_bounded(  # noqa: N802
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Verify _get_steps issues at most a constant number of queries (N+1 guard).

        With N=10 steps, _get_steps issues:
          1 query for projects (get_project_or_404)
          1 query for work_items
          1 query for batch_items (_get_batch_item for synthetic steps)
          1 query for workflow_steps
          1 query for fix_cycle_counts (GROUP BY step_id)
          2 queries for _aggregate_step_spans (one per table, GROUP BY step_id)
          N queries for step_runs (one per step, for error_message + run_count)

        Total: 7 + N = 17 queries for N=10. The key N+1 prevention is the 2 bulk
        GROUP BY queries — without them there would be 7 + 2N queries.
        """
        project = test_project
        item_id = "I-00034"
        _make_work_item(db_session, project.id, item_id)

        steps = []
        for i in range(10):
            step = WorkflowStep(
                project_id=project.id,
                work_item_id=item_id,
                step_number=i + 1,
                step_id=f"S{i:02d}",
                agent_label="Backend",
                step_type=StepType.implementation,
                status=StepStatus.completed,
                started_at=datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC),
                completed_at=datetime(2026, 4, 22, 12, 0, 10, tzinfo=UTC),
            )
            db_session.add(step)
            db_session.flush()
            steps.append(step)
            make_step_run(
                db_session,
                step_id=step.id,
                run_number=1,
                status=RunStatus.completed,
                started_at=datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC),
                completed_at=datetime(2026, 4, 22, 12, 0, 10, tzinfo=UTC),
            )

        query_count = 0

        @event.listens_for(db_session.get_bind(), "before_cursor_execute")
        def count_queries(
            _conn: object,
            _cursor: object,
            statement: str,
            _params: object,
            _context: object,
            _executemany: object,
        ) -> None:
            """Increment query_count each time a SQL statement is executed."""
            nonlocal query_count
            query_count += 1

        try:
            _get_steps(project.id, item_id, db_session)
        finally:
            event.remove(db_session.get_bind(), "before_cursor_execute", count_queries)

        max_allowed = 17
        assert query_count <= max_allowed, (
            f"Expected ≤{max_allowed} queries, got {query_count} — possible N+1 regression"
        )
