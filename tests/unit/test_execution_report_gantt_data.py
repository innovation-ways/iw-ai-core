"""Unit tests for Gantt data computation: _compute_gantt_pcts and _gantt_class_for_run.

Tests percentage calculations, class assignment rules, and boundary conditions.
"""

from __future__ import annotations

from datetime import UTC, datetime

from orch.daemon.execution_report import (
    StepRunSegment,
    _compute_gantt_pcts,
    _gantt_class_for_run,
)
from orch.db.models import RunStatus


def make_segment(
    run_number: int = 1,
    status: RunStatus = RunStatus.completed,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    duration_secs: float = 60.0,
) -> StepRunSegment:
    if started_at is None:
        started_at = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
    actual_completed = completed_at
    if actual_completed is None and status not in (
        RunStatus.running,
        RunStatus.pending,
        RunStatus.stalled,
    ):
        actual_completed = datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC)
    return StepRunSegment(
        run_number=run_number,
        status=status,
        started_at=started_at,
        completed_at=actual_completed,
        duration_secs=duration_secs,
        error_message=None,
        report_file=None,
        report_content=None,
        is_final_attempt=False,
        gantt_class="completed",
        left_pct=0.0,
        width_pct=10.0,
    )


class TestGanttClassForRun:
    """Test _gantt_class_for_run gantt class assignment rules."""

    def test_non_final_run_gets_retry_class(self) -> None:
        segment = make_segment(run_number=1)
        result = _gantt_class_for_run(segment, max_run_number=3)
        assert result == "retry"

    def test_final_run_completed_gets_completed_class(self) -> None:
        segment = make_segment(run_number=3, status=RunStatus.completed)
        result = _gantt_class_for_run(segment, max_run_number=3)
        assert result == "completed"

    def test_final_run_failed_gets_failed_class(self) -> None:
        segment = make_segment(run_number=3, status=RunStatus.failed)
        result = _gantt_class_for_run(segment, max_run_number=3)
        assert result == "failed"

    def test_final_run_timeout_gets_skipped_class(self) -> None:
        segment = make_segment(run_number=2, status=RunStatus.timeout)
        result = _gantt_class_for_run(segment, max_run_number=2)
        assert result == "skipped"

    def test_running_final_run_gets_in_progress_class(self) -> None:
        segment = make_segment(
            run_number=2,
            status=RunStatus.running,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=None,
        )
        result = _gantt_class_for_run(segment, max_run_number=2)
        assert result == "in_progress"

    def test_pending_run_gets_in_progress_class(self) -> None:
        segment = make_segment(run_number=1, status=RunStatus.pending)
        result = _gantt_class_for_run(segment, max_run_number=1)
        assert result == "in_progress"

    def test_stalled_run_gets_in_progress_class(self) -> None:
        segment = make_segment(run_number=1, status=RunStatus.stalled)
        result = _gantt_class_for_run(segment, max_run_number=1)
        assert result == "in_progress"

    def test_killed_run_gets_skipped_class(self) -> None:
        segment = make_segment(run_number=1, status=RunStatus.killed)
        result = _gantt_class_for_run(segment, max_run_number=1)
        assert result == "skipped"


class TestComputeGanttPctsBasic:
    """Test _compute_gantt_pcts basic functionality."""

    def test_zero_total_duration_returns_zero(self) -> None:
        left, width = _compute_gantt_pcts(
            datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC),
            datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            total_duration=0.0,
        )
        assert (left, width) == (0.0, 0.0)

    def test_none_started_at_returns_zero(self) -> None:
        left, width = _compute_gantt_pcts(
            None,
            datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC),
            datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            total_duration=3600.0,
        )
        assert (left, width) == (0.0, 0.0)

    def test_full_duration_segment(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC)
        left, width = _compute_gantt_pcts(started, completed, item_start, 3600.0)
        assert left == 0.0
        assert width == 100.0

    def test_middle_segment(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 1, 10, 30, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC)
        left, width = _compute_gantt_pcts(started, completed, item_start, 3600.0)
        assert 49.0 <= left <= 51.0
        assert 49.0 <= width <= 51.0


class TestComputeGanttPctsBoundaryConditions:
    """Boundary conditions: minimum width enforcement, sum constraint."""

    def test_sub_second_run_gets_minimum_0_5_percent_width(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 1, 10, 0, 0, 100, tzinfo=UTC)
        left, width = _compute_gantt_pcts(started, completed, item_start, 3600.0)
        assert width >= 0.5

    def test_left_pct_clamped_to_100_max(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 1, 13, 0, 0, tzinfo=UTC)
        left, width = _compute_gantt_pcts(started, completed, item_start, 3600.0)
        assert left <= 100.0

    def test_left_pct_not_negative(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 1, 9, 0, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        left, width = _compute_gantt_pcts(started, completed, item_start, 3600.0)
        assert left >= 0.0

    def test_left_plus_width_never_exceeds_100(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 1, 11, 30, 0, tzinfo=UTC)
        left, width = _compute_gantt_pcts(started, completed, item_start, 3600.0)
        assert left + width <= 100.0


class TestComputeGanttPctsRounding:
    """Rounding to 2 decimal places."""

    def test_results_are_float(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 1, 10, 15, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 1, 10, 45, 0, tzinfo=UTC)
        left, width = _compute_gantt_pcts(started, completed, item_start, 3600.0)
        assert isinstance(left, float)
        assert isinstance(width, float)

    def test_results_rounded_to_two_decimals(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 1, 10, 17, 43, tzinfo=UTC)
        completed = datetime(2025, 1, 1, 10, 52, 19, tzinfo=UTC)
        left, width = _compute_gantt_pcts(started, completed, item_start, 3600.0)
        assert round(left, 2) == left
        assert round(width, 2) == width


class TestSegmentsPerStepOrderedByRunNumber:
    """Segments generated in run_number order per step."""

    def test_segments_ordered_by_run_number(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        from orch.daemon.execution_report import _compute_gantt_pcts

        runs_data = [
            (
                1,
                datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
                datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC),
            ),
            (
                2,
                datetime(2025, 1, 1, 10, 5, 0, tzinfo=UTC),
                datetime(2025, 1, 1, 10, 6, 0, tzinfo=UTC),
            ),
            (
                3,
                datetime(2025, 1, 1, 10, 10, 0, tzinfo=UTC),
                datetime(2025, 1, 1, 10, 11, 0, tzinfo=UTC),
            ),
        ]
        segments = []
        for run_number, started, completed in runs_data:
            left, width = _compute_gantt_pcts(started, completed, item_start, 3600.0)
            seg = StepRunSegment(
                run_number=run_number,
                status=RunStatus.completed,
                started_at=started,
                completed_at=completed,
                duration_secs=60.0,
                error_message=None,
                report_file=None,
                report_content=None,
                is_final_attempt=(run_number == 3),
                gantt_class="completed",
                left_pct=left,
                width_pct=width,
            )
            segments.append(seg)

        assert segments[0].run_number == 1
        assert segments[1].run_number == 2
        assert segments[2].run_number == 3


class TestZeroDurationItem:
    """Zero-duration item (no StepRun rows) produces zero percentages without raising."""

    def test_zero_duration_no_runs_returns_zero_pcts(self) -> None:
        left, width = _compute_gantt_pcts(None, None, datetime.now(UTC), 0.0)
        assert left == 0.0
        assert width == 0.0

    def test_zero_duration_with_started_at_but_no_completed(self) -> None:
        now = datetime.now(UTC)
        left, width = _compute_gantt_pcts(now, None, now, 0.0)
        assert left == 0.0
        assert width == 0.0


class TestFixCycleEntryGanttPcts:
    """FixCycleEntry left_pct / width_pct are precomputed by same function."""

    def test_fix_cycle_entry_uses_same_pct_computation(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 1, 10, 30, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC)
        left, width = _compute_gantt_pcts(started, completed, item_start, 3600.0)
        assert 49.0 <= left <= 51.0
        assert 49.0 <= width <= 51.0


class TestMultipleSegmentsSumConstraint:
    """Sum of width_pct across a step's segments never exceeds 100%."""

    def test_multiple_segments_sum_leq_100(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        total_duration = 3600.0

        segments_data = [
            (
                datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
                datetime(2025, 1, 1, 10, 15, 0, tzinfo=UTC),
            ),
            (
                datetime(2025, 1, 1, 10, 15, 0, tzinfo=UTC),
                datetime(2025, 1, 1, 10, 30, 0, tzinfo=UTC),
            ),
            (
                datetime(2025, 1, 1, 10, 30, 0, tzinfo=UTC),
                datetime(2025, 1, 1, 11, 00, 0, tzinfo=UTC),
            ),
            (
                datetime(2025, 1, 1, 11, 00, 0, tzinfo=UTC),
                datetime(2025, 1, 1, 11, 15, 0, tzinfo=UTC),
            ),
        ]

        for i, (started, completed) in enumerate(segments_data):
            left, width = _compute_gantt_pcts(started, completed, item_start, total_duration)
            assert left + width <= 100.0, (
                f"Segment {i}: left={left}, width={width} violates constraint"
            )


class TestInProgressSegment:
    """In-progress segment (NULL completed_at) gets in_progress class."""

    def test_in_progress_segment_class(self) -> None:
        segment = StepRunSegment(
            run_number=2,
            status=RunStatus.running,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=None,
            duration_secs=None,
            error_message=None,
            report_file=None,
            report_content=None,
            is_final_attempt=False,
            gantt_class="in_progress",
            left_pct=0.0,
            width_pct=50.0,
        )
        result = _gantt_class_for_run(segment, max_run_number=2)
        assert result == "in_progress"

    def test_in_progress_segment_with_now_as_completed(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        left, width = _compute_gantt_pcts(
            datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            None,
            item_start,
            3600.0,
        )
        assert left >= 0.0
        assert width >= 0.5
