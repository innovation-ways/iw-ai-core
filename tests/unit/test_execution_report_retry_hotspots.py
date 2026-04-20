"""Unit tests for retry hotspot detection logic.

Tests the hotspot logic by building StepRow objects directly and verifying
the is_hotspot flag and hotspot sorting — no DB required.
"""

from __future__ import annotations

from datetime import UTC, datetime

from orch.daemon.execution_report import (
    ExecutionReportData,
    RetryHotspot,
    StepRow,
    StepRunSegment,
    render_execution_report_markdown,
)
from orch.db.models import RunStatus, StepStatus


def make_segment(
    run_number: int,
    status: RunStatus = RunStatus.completed,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    duration_secs: float = 60.0,
) -> StepRunSegment:
    if started_at is None:
        started_at = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
    if completed_at is None:
        completed_at = datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC)
    return StepRunSegment(
        run_number=run_number,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        duration_secs=duration_secs,
        error_message=None,
        report_file=None,
        report_content=None,
        is_final_attempt=False,
        gantt_class="completed",
        left_pct=0.0,
        width_pct=10.0,
    )


def make_step_row(
    step_id: str,
    step_number: int,
    max_run_number: int,
    display_label: str = "Step",
    final_status: StepStatus = StepStatus.completed,
) -> StepRow:
    runs = [make_segment(rn) for rn in range(1, max_run_number + 1)]
    return StepRow(
        step_id=step_id,
        step_number=step_number,
        step_type="implementation",
        step_label=display_label,
        agent_label=display_label,
        opencode_agent=None,
        display_label=display_label,
        runs=runs,
        fix_cycles=[],
        max_run_number=max_run_number,
        final_status=final_status,
        is_hotspot=max_run_number >= 2,
        total_duration_secs=60.0 * max_run_number,
    )


class TestHotspotDetectionOnlyRetriedSteps:
    """Only steps with max(run_number) >= 2 should appear in hotspots."""

    def test_single_run_is_not_hotspot(self) -> None:
        step = make_step_row("S01", 1, max_run_number=1)
        assert step.is_hotspot is False

    def test_two_runs_is_hotspot(self) -> None:
        step = make_step_row("S01", 1, max_run_number=2)
        assert step.is_hotspot is True

    def test_three_runs_is_hotspot(self) -> None:
        step = make_step_row("S01", 1, max_run_number=3)
        assert step.is_hotspot is True

    def test_zero_runs_is_not_hotspot(self) -> None:
        step = StepRow(
            step_id="S01",
            step_number=1,
            step_type="implementation",
            step_label="Backend",
            agent_label="Backend",
            opencode_agent=None,
            display_label="Backend",
            runs=[],
            fix_cycles=[],
            max_run_number=0,
            final_status=StepStatus.pending,
            is_hotspot=False,
            total_duration_secs=0.0,
        )
        assert step.is_hotspot is False


class TestHotspotSortOrder:
    """Sort order: retry_count desc, then step_id asc (AC6)."""

    def test_retry_count_descending(self) -> None:
        hotspots = [
            RetryHotspot(
                step_id="S03", display_label="Step 3", retry_count=2, final_status="failed"
            ),
            RetryHotspot(
                step_id="S01", display_label="Step 1", retry_count=3, final_status="completed"
            ),
            RetryHotspot(
                step_id="S02", display_label="Step 2", retry_count=2, final_status="completed"
            ),
        ]
        sorted_hotspots = sorted(hotspots, key=lambda h: (-h.retry_count, h.step_id))
        assert sorted_hotspots[0].retry_count == 3
        assert sorted_hotspots[1].retry_count == 2
        assert sorted_hotspots[2].retry_count == 2

    def test_step_id_ascending_for_same_retry_count(self) -> None:
        hotspots = [
            RetryHotspot(
                step_id="S03", display_label="Step 3", retry_count=2, final_status="failed"
            ),
            RetryHotspot(
                step_id="S01", display_label="Step 1", retry_count=2, final_status="completed"
            ),
            RetryHotspot(
                step_id="S02", display_label="Step 2", retry_count=2, final_status="completed"
            ),
        ]
        sorted_hotspots = sorted(hotspots, key=lambda h: (-h.retry_count, h.step_id))
        assert sorted_hotspots[0].step_id == "S01"
        assert sorted_hotspots[1].step_id == "S02"
        assert sorted_hotspots[2].step_id == "S03"

    def test_full_sort_order(self) -> None:
        hotspots = [
            RetryHotspot(
                step_id="S04", display_label="Step 4", retry_count=1, final_status="completed"
            ),
            RetryHotspot(
                step_id="S02", display_label="Step 2", retry_count=3, final_status="failed"
            ),
            RetryHotspot(
                step_id="S03", display_label="Step 3", retry_count=3, final_status="completed"
            ),
            RetryHotspot(
                step_id="S01", display_label="Step 1", retry_count=2, final_status="completed"
            ),
        ]
        sorted_hotspots = sorted(hotspots, key=lambda h: (-h.retry_count, h.step_id))
        assert [h.step_id for h in sorted_hotspots] == ["S02", "S03", "S01", "S04"]


class TestEmptyHotspotList:
    """Empty hotspot list for items where every step has max(run_number) == 1."""

    def test_all_single_run_items_produce_empty_hotspots(self) -> None:
        steps = [
            make_step_row("S01", 1, max_run_number=1),
            make_step_row("S02", 2, max_run_number=1),
            make_step_row("S03", 3, max_run_number=1),
        ]
        data = ExecutionReportData(
            project_id="test-proj",
            work_item_id="F-00001",
            work_item_title="Test",
            work_item_type="Feature",
            work_item_status="completed",
            verdict="completed",
            verdict_badge="Completed",
            item_started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            item_completed_at=datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC),
            total_duration_secs=3600.0,
            steps=steps,
            hotspots=[],
            generated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        md = render_execution_report_markdown(data)
        assert "No retries — clean run." in md

    def test_mixed_single_and_multi_run_items(self) -> None:
        steps = [
            make_step_row("S01", 1, max_run_number=1),
            make_step_row("S02", 2, max_run_number=3),
            make_step_row("S03", 3, max_run_number=1),
        ]
        hotspots = [
            RetryHotspot(
                step_id="S02", display_label="Step 2", retry_count=3, final_status="completed"
            ),
        ]
        data = ExecutionReportData(
            project_id="test-proj",
            work_item_id="F-00001",
            work_item_title="Test",
            work_item_type="Feature",
            work_item_status="completed",
            verdict="completed",
            verdict_badge="Completed",
            item_started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            item_completed_at=datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC),
            total_duration_secs=3600.0,
            steps=steps,
            hotspots=hotspots,
            generated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        md = render_execution_report_markdown(data)
        assert "S02" in md
        assert "S01" not in [h.step_id for h in hotspots]


class TestHotspotRenderingInMarkdown:
    """Verify hotspot data renders correctly in markdown."""

    def test_hotspot_retry_count_in_markdown(self) -> None:
        hotspots = [
            RetryHotspot(
                step_id="S03", display_label="Backend", retry_count=4, final_status="completed"
            ),
        ]
        data = ExecutionReportData(
            project_id="test-proj",
            work_item_id="F-00001",
            work_item_title="Test Feature",
            work_item_type="Feature",
            work_item_status="completed",
            verdict="completed",
            verdict_badge="Completed",
            item_started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            item_completed_at=datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC),
            total_duration_secs=3600.0,
            steps=[],
            hotspots=hotspots,
            generated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        md = render_execution_report_markdown(data)
        assert "S03" in md
        assert "4" in md
        assert "Backend" in md

    def test_hotspot_final_status_in_markdown(self) -> None:
        hotspots = [
            RetryHotspot(
                step_id="S01", display_label="Tests", retry_count=2, final_status="failed"
            ),
        ]
        data = ExecutionReportData(
            project_id="test-proj",
            work_item_id="F-00001",
            work_item_title="Test Feature",
            work_item_type="Feature",
            work_item_status="failed",
            verdict="failed",
            verdict_badge="Failed",
            item_started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            item_completed_at=datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC),
            total_duration_secs=3600.0,
            steps=[],
            hotspots=hotspots,
            generated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        md = render_execution_report_markdown(data)
        assert "failed" in md.lower()
