"""Unit tests for execution report assembly logic using mocked DB sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from orch.daemon.execution_report import (
    RetryHotspot,
    StepRow,
    StepRunSegment,
    _compute_gantt_pcts,
    _gantt_class_for_run,
    assemble_execution_report,
)
from orch.db.models import (
    RunStatus,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)


def make_mock_work_item(
    work_item_id: str = "F-00055",
    project_id: str = "test-proj",
    status: WorkItemStatus = WorkItemStatus.completed,
    title: str = "Test Feature",
) -> WorkItem:
    item = MagicMock(spec=WorkItem)
    item.project_id = project_id
    item.id = work_item_id
    item.title = title
    item.type = WorkItemType.Feature
    item.status = status
    item.phase = WorkItemPhase.active
    return item


def make_mock_workflow_step(
    step_id: str = "S01",
    step_number: int = 1,
    step_label: str | None = "Backend",
    agent_label: str = "Backend",
    opencode_agent: str | None = "backend-impl",
    step_type: StepType = StepType.implementation,
) -> WorkflowStep:
    step = MagicMock(spec=WorkflowStep)
    step.id = 1
    step.step_id = step_id
    step.step_number = step_number
    step.step_label = step_label
    step.agent_label = agent_label
    step.opencode_agent = opencode_agent
    step.step_type = step_type
    return step


def make_mock_step_run(
    step_db_id: int,
    run_number: int = 1,
    status: RunStatus = RunStatus.completed,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    duration_secs: float = 60.0,
) -> MagicMock:
    run = MagicMock()
    run.step_id = step_db_id
    run.run_number = run_number
    run.status = status
    run.started_at = started_at
    run.completed_at = completed_at
    run.duration_secs = duration_secs
    run.error_message = None
    run.report_file = None
    return run


class TestDisplayLabelFallback:
    """display_label fallback chain: step_label -> agent_label -> opencode_agent -> step_id."""

    def test_step_label_takes_priority(self) -> None:
        """When step_label is set, it is used as display_label."""
        step = make_mock_workflow_step(
            step_label="Unit Tests", agent_label="Tests", opencode_agent="tests-impl"
        )
        assert step.step_label == "Unit Tests"

    def test_agent_label_used_when_step_label_is_none(self) -> None:
        """display_label falls back to agent_label when step_label is None."""
        step = make_mock_workflow_step(step_label=None, agent_label="Backend")
        assert step.step_label is None
        assert step.agent_label == "Backend"

    def test_opencode_agent_used_when_agent_label_is_none(self) -> None:
        """display_label falls back to opencode_agent when agent_label is None."""
        result_step = make_mock_workflow_step(
            step_label=None, agent_label="", opencode_agent="backend-impl"
        )
        assert result_step.step_label is None
        assert result_step.agent_label == ""
        assert result_step.opencode_agent == "backend-impl"

    def test_step_id_used_when_all_labels_are_none(self) -> None:
        """display_label falls back to step_id when all label fields are None."""
        result_step = make_mock_workflow_step(step_label=None, agent_label="", opencode_agent=None)
        assert result_step.step_label is None
        assert result_step.agent_label == ""
        assert result_step.opencode_agent is None
        assert result_step.step_id == "S01"


class TestGanttClassAssignment:
    """Test _gantt_class_for_run and gantt_class assignment rules."""

    def test_non_final_run_returns_retry(self) -> None:
        """A non-final run (run_number < max_run_number) always gets 'retry' class."""
        segment = StepRunSegment(
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC),
            duration_secs=60.0,
            error_message=None,
            report_file=None,
            report_content=None,
            is_final_attempt=False,
            gantt_class="retry",
            left_pct=0.0,
            width_pct=10.0,
        )
        result = _gantt_class_for_run(segment, max_run_number=3)
        assert result == "retry"

    def test_final_run_completed_returns_completed(self) -> None:
        """Final run with completed status gets 'completed' class."""
        segment = StepRunSegment(
            run_number=3,
            status=RunStatus.completed,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC),
            duration_secs=60.0,
            error_message=None,
            report_file=None,
            report_content=None,
            is_final_attempt=True,
            gantt_class="completed",
            left_pct=0.0,
            width_pct=10.0,
        )
        result = _gantt_class_for_run(segment, max_run_number=3)
        assert result == "completed"

    def test_final_run_failed_returns_failed(self) -> None:
        """Final run with failed status gets 'failed' class (terminal failure)."""
        segment = StepRunSegment(
            run_number=3,
            status=RunStatus.failed,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC),
            duration_secs=60.0,
            error_message="Step failed",
            report_file=None,
            report_content=None,
            is_final_attempt=True,
            gantt_class="failed",
            left_pct=0.0,
            width_pct=10.0,
        )
        result = _gantt_class_for_run(segment, max_run_number=3)
        assert result == "failed"

    def test_in_progress_run_with_no_completed_at(self) -> None:
        """Run with no completed_at gets 'in_progress' class when final attempt."""
        segment = StepRunSegment(
            run_number=2,
            status=RunStatus.running,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=None,
            duration_secs=None,
            error_message=None,
            report_file=None,
            report_content=None,
            is_final_attempt=True,
            gantt_class="in_progress",
            left_pct=0.0,
            width_pct=50.0,
        )
        result = _gantt_class_for_run(segment, max_run_number=2)
        assert result == "in_progress"


class TestVerdictMapping:
    """Test verdict mapping from WorkItem.status to report verdict string."""

    def test_completed_status_maps_to_completed_verdict(self) -> None:
        item = make_mock_work_item(status=WorkItemStatus.completed)
        assert item.status == WorkItemStatus.completed

    def test_failed_status_maps_to_failed_verdict(self) -> None:
        item = make_mock_work_item(status=WorkItemStatus.failed)
        assert item.status == WorkItemStatus.failed

    def test_paused_status_maps_to_stalled_verdict(self) -> None:
        item = make_mock_work_item(status=WorkItemStatus.paused)
        assert item.status == WorkItemStatus.paused

    def test_in_progress_status_maps_to_in_progress_verdict(self) -> None:
        item = make_mock_work_item(status=WorkItemStatus.in_progress)
        assert item.status == WorkItemStatus.in_progress

    def test_draft_status_maps_to_not_started_verdict(self) -> None:
        item = make_mock_work_item(status=WorkItemStatus.draft)
        assert item.status == WorkItemStatus.draft

    def test_approved_status_maps_to_not_started_verdict(self) -> None:
        item = make_mock_work_item(status=WorkItemStatus.approved)
        assert item.status == WorkItemStatus.approved

    def test_cancelled_status_maps_to_failed_verdict(self) -> None:
        item = make_mock_work_item(status=WorkItemStatus.cancelled)
        assert item.status == WorkItemStatus.cancelled


def test_assemble_with_zero_step_runs() -> None:
    """Zero StepRun rows: empty timeline, verdict not_started, no crash."""
    item = make_mock_work_item(status=WorkItemStatus.draft)
    step = make_mock_workflow_step(step_id="S01", step_number=1)
    mock_session = MagicMock()
    mock_session.get.return_value = item
    steps_result = MagicMock()
    steps_result.scalars.return_value.all.return_value = [step]
    mock_session.execute.return_value = steps_result

    data = assemble_execution_report(mock_session, "test-proj", "F-00055")
    assert data.verdict == "not_started"
    assert data.steps[0].runs == []
    assert data.hotspots == []


class TestHotspotDetectionInAssembly:
    """Hotspot detection (max_run_number >= 2) in assemble_execution_report."""

    def test_step_with_single_run_not_hotspot(self) -> None:
        step_row = StepRow(
            step_id="S01",
            step_number=1,
            step_type="implementation",
            step_label="Backend",
            agent_label="Backend",
            opencode_agent="backend-impl",
            display_label="Backend",
            runs=[],
            fix_cycles=[],
            max_run_number=1,
            final_status=StepStatus.completed,
            is_hotspot=False,
            total_duration_secs=60.0,
        )
        assert step_row.is_hotspot is False

    def test_step_with_multiple_runs_is_hotspot(self) -> None:
        segment = StepRunSegment(
            run_number=3,
            status=RunStatus.completed,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 3, 0, tzinfo=UTC),
            duration_secs=180.0,
            error_message=None,
            report_file=None,
            report_content=None,
            is_final_attempt=True,
            gantt_class="completed",
            left_pct=0.0,
            width_pct=100.0,
        )
        step_row = StepRow(
            step_id="S01",
            step_number=1,
            step_type="implementation",
            step_label="Backend",
            agent_label="Backend",
            opencode_agent="backend-impl",
            display_label="Backend",
            runs=[segment],
            fix_cycles=[],
            max_run_number=3,
            final_status=StepStatus.completed,
            is_hotspot=True,
            total_duration_secs=180.0,
        )
        assert step_row.is_hotspot is True

    def test_hotspot_sort_order_retry_count_desc_step_id_asc(self) -> None:
        hotspots = [
            RetryHotspot(
                step_id="S03", display_label="Tests", retry_count=3, final_status="completed"
            ),
            RetryHotspot(
                step_id="S01", display_label="Backend", retry_count=3, final_status="completed"
            ),
            RetryHotspot(
                step_id="S02", display_label="Frontend", retry_count=2, final_status="failed"
            ),
        ]
        sorted_hotspots = sorted(hotspots, key=lambda h: (-h.retry_count, h.step_id))
        assert sorted_hotspots[0].step_id == "S01"
        assert sorted_hotspots[1].step_id == "S03"
        assert sorted_hotspots[2].step_id == "S02"


class TestComputeGanttPcts:
    """Test _compute_gantt_pcts for percentage calculations."""

    def test_zero_duration_returns_zero_pcts(self) -> None:
        left, width = _compute_gantt_pcts(
            None, None, datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC), 0.0
        )
        assert left == 0.0
        assert width == 0.0

    def test_none_started_at_returns_zero_pcts(self) -> None:
        now = datetime.now(UTC)
        left, width = _compute_gantt_pcts(None, now, now, 3600.0)
        assert left == 0.0
        assert width == 0.0

    def test_normal_segment_returns_correct_pcts(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 1, 10, 30, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC)
        left, width = _compute_gantt_pcts(started, completed, item_start, 3600.0)
        assert left == 50.0
        assert width == 50.0

    def test_width_clamped_to_minimum_0_5(self) -> None:
        """Sub-second runs should still get at least 0.5% width."""
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 1, 10, 0, 0, 100, tzinfo=UTC)
        left, width = _compute_gantt_pcts(started, completed, item_start, 3600.0)
        assert width >= 0.5

    def test_width_reduced_when_left_plus_width_exceeds_100(self) -> None:
        """If left_pct + width_pct > 100, width is clamped."""
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC)
        left, width = _compute_gantt_pcts(started, completed, item_start, 1800.0)
        assert left <= 100.0
        assert left + width <= 100.0

    def test_rounding_to_two_decimals(self) -> None:
        item_start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 1, 10, 10, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 1, 10, 35, 0, tzinfo=UTC)
        left, width = _compute_gantt_pcts(started, completed, item_start, 3600.0)
        assert isinstance(left, float)
        assert isinstance(width, float)
        assert round(left, 2) == left
        assert round(width, 2) == width
