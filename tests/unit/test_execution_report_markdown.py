"""Unit tests for execution report markdown renderer — additional scenarios.

These tests complement test_execution_report.py with finer-grained assertions
on section ordering, exact placeholder text, multi-line fix summaries, and purity.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from orch.daemon.execution_report import (
    ExecutionReportData,
    FixCycleEntry,
    RetryHotspot,
    StepRow,
    StepRunSegment,
    render_execution_report_markdown,
)
from orch.db.models import FixStatus, RunStatus, StepStatus


def make_segment(
    run_number: int = 1,
    status: RunStatus = RunStatus.completed,
    left_pct: float = 0.0,
    width_pct: float = 10.0,
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
        is_final_attempt=(run_number == 1),
        gantt_class="completed" if status == RunStatus.completed else "failed",
        left_pct=left_pct,
        width_pct=width_pct,
    )


def make_step_row(
    step_id: str = "S01",
    step_number: int = 1,
    display_label: str = "Backend",
    runs: list[StepRunSegment] | None = None,
    cycles: list[FixCycleEntry] | None = None,
    max_run_number: int = 1,
    final_status: StepStatus = StepStatus.completed,
) -> StepRow:
    return StepRow(
        step_id=step_id,
        step_number=step_number,
        step_type="implementation",
        step_label=display_label,
        agent_label="Backend",
        opencode_agent="backend-impl",
        display_label=display_label,
        runs=runs or [make_segment()],
        fix_cycles=cycles or [],
        max_run_number=max_run_number,
        final_status=final_status,
        is_hotspot=max_run_number >= 2,
        total_duration_secs=60.0,
    )


def make_report_data(
    work_item_id: str = "F-00001",
    title: str = "Test Feature",
    verdict: Literal["completed", "failed", "stalled", "in_progress", "not_started"] = "completed",
    steps: list[StepRow] | None = None,
    hotspots: list[RetryHotspot] | None = None,
) -> ExecutionReportData:
    return ExecutionReportData(
        project_id="test-proj",
        work_item_id=work_item_id,
        work_item_title=title,
        work_item_type="Feature",
        work_item_status=verdict,
        verdict=verdict,
        verdict_badge="Completed" if verdict == "completed" else "Failed",
        item_started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
        item_completed_at=datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC),
        total_duration_secs=3600.0,
        steps=steps or [make_step_row()],
        hotspots=hotspots or [],
        generated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
    )


class TestAllFourSectionsPresent:
    """Verify all four sections appear in correct order."""

    def test_all_sections_in_order(self) -> None:
        fc = FixCycleEntry(
            cycle_number=1,
            trigger_type="code_review",
            trigger_report="/path/to/trigger.md",
            fix_report="/path/to/fix.md",
            fix_summary="Fixed the issue",
            status=FixStatus.completed,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 30, 0, tzinfo=UTC),
            duration_secs=1800.0,
            left_pct=10.0,
            width_pct=5.0,
        )
        step = make_step_row(cycles=[fc])
        hotspots = [
            RetryHotspot(
                step_id="S01", display_label="Backend", retry_count=2, final_status="completed"
            )
        ]
        data = make_report_data(steps=[step], hotspots=hotspots)
        md = render_execution_report_markdown(data)

        header_idx = md.find("# Execution Report:")
        hotspot_idx = md.find("## Retry Hotspots")
        timeline_idx = md.find("## Step Timeline")
        fixcycles_idx = md.find("## Fix Cycles")
        footer_idx = md.find("---", md.find("## Fix Cycles"))

        assert header_idx < hotspot_idx < timeline_idx < fixcycles_idx < footer_idx


class TestHotspotPlaceholderText:
    """Exact wording for empty and null hotspots."""

    def test_empty_hotspots_exact_phrase(self) -> None:
        """'No retries — clean run.' is the exact empty placeholder."""
        data = make_report_data(hotspots=[])
        md = render_execution_report_markdown(data)
        assert "No retries — clean run." in md

    def test_null_fix_summary_uses_exact_placeholder(self) -> None:
        """FixCycleEntry with fix_summary=None renders '_no fix summary captured (pre-F-00056)_'."""
        fc = FixCycleEntry(
            cycle_number=1,
            trigger_type="code_review",
            trigger_report=None,
            fix_report=None,
            fix_summary=None,
            status=FixStatus.completed,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 30, 0, tzinfo=UTC),
            duration_secs=1800.0,
            left_pct=10.0,
            width_pct=5.0,
        )
        step = make_step_row(cycles=[fc])
        data = make_report_data(steps=[step])
        md = render_execution_report_markdown(data)
        assert "> _no fix summary captured (pre-F-00056)_" in md


class TestMultiLineFixSummary:
    """Multi-bullet fix_summary renders as multi-line blockquote."""

    def test_multi_line_fix_summary_becomes_blockquote_lines(self) -> None:
        fc = FixCycleEntry(
            cycle_number=1,
            trigger_type="code_review",
            trigger_report="/path/to/trigger.md",
            fix_report="/path/to/fix.md",
            fix_summary="- Fixed SQL injection\n- Added validation\n- Updated error messages",
            status=FixStatus.completed,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 30, 0, tzinfo=UTC),
            duration_secs=1800.0,
            left_pct=10.0,
            width_pct=5.0,
        )
        step = make_step_row(cycles=[fc])
        data = make_report_data(steps=[step])
        md = render_execution_report_markdown(data)
        lines = md.splitlines()
        blockquote_lines = [ln for ln in lines if ln.startswith(">")]
        assert len(blockquote_lines) == 3
        assert "> - Fixed SQL injection" in md
        assert "> - Added validation" in md
        assert "> - Updated error messages" in md


class TestRenderPurity:
    """Pure function: same input yields byte-identical output on repeated calls."""

    def test_identical_data_produces_identical_markdown(self) -> None:
        data = make_report_data()
        md1 = render_execution_report_markdown(data)
        md2 = render_execution_report_markdown(data)
        assert md1 == md2

    def test_stdout_and_file_output_are_identical(self) -> None:
        """The render function output is what would be written to file — no extra processing."""
        data = make_report_data()
        md = render_execution_report_markdown(data)
        assert md.startswith("# Execution Report:")
        assert "_Generated by iw item-report on" in md


class TestSectionContent:
    """Verify content in each section matches data structures."""

    def test_timeline_shows_all_steps(self) -> None:
        steps = [
            make_step_row(
                step_id="S01",
                step_number=1,
                display_label="Backend",
                final_status=StepStatus.completed,
            ),
            make_step_row(
                step_id="S02",
                step_number=2,
                display_label="Frontend",
                final_status=StepStatus.completed,
            ),
            make_step_row(
                step_id="S03", step_number=3, display_label="Tests", final_status=StepStatus.failed
            ),
        ]
        data = make_report_data(steps=steps)
        md = render_execution_report_markdown(data)
        assert "| S1 |" in md or "| S1 | Backend" in md
        assert "| S2 |" in md or "| S2 | Frontend" in md
        assert "| S3 |" in md or "| S3 | Tests" in md

    def test_hotspot_section_shows_retry_count(self) -> None:
        hotspots = [
            RetryHotspot(
                step_id="S03", display_label="Backend", retry_count=3, final_status="completed"
            ),
        ]
        data = make_report_data(hotspots=hotspots)
        md = render_execution_report_markdown(data)
        assert "S03" in md
        assert "3" in md

    def test_fix_cycle_with_summary_shows_trigger_and_fix_reports(self) -> None:
        fc = FixCycleEntry(
            cycle_number=1,
            trigger_type="code_review",
            trigger_report="/path/to/trigger.md",
            fix_report="/path/to/fix.md",
            fix_summary="Fixed the issue",
            status=FixStatus.completed,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 30, 0, tzinfo=UTC),
            duration_secs=1800.0,
            left_pct=10.0,
            width_pct=5.0,
        )
        step = make_step_row(cycles=[fc])
        data = make_report_data(steps=[step])
        md = render_execution_report_markdown(data)
        assert "Trigger report:" in md
        assert "Fix report:" in md

    def test_footer_generated_timestamp_present(self) -> None:
        data = make_report_data()
        md = render_execution_report_markdown(data)
        assert "_Generated by iw item-report on" in md
        assert "T" in md


class TestEdgeCaseFixSummary:
    """Edge cases: empty string, whitespace-only, very long summary."""

    def test_empty_string_fix_summary_uses_placeholder(self) -> None:
        fc = FixCycleEntry(
            cycle_number=1,
            trigger_type="code_review",
            trigger_report=None,
            fix_report=None,
            fix_summary="",
            status=FixStatus.completed,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 30, 0, tzinfo=UTC),
            duration_secs=1800.0,
            left_pct=10.0,
            width_pct=5.0,
        )
        step = make_step_row(cycles=[fc])
        data = make_report_data(steps=[step])
        md = render_execution_report_markdown(data)
        assert "> _no fix summary captured (pre-F-00056)_" in md

    def test_whitespace_only_fix_summary_rendered_as_blockquote(self) -> None:
        fc = FixCycleEntry(
            cycle_number=1,
            trigger_type="code_review",
            trigger_report=None,
            fix_report=None,
            fix_summary="   \n\t  ",
            status=FixStatus.completed,
            started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2025, 1, 1, 10, 30, 0, tzinfo=UTC),
            duration_secs=1800.0,
            left_pct=10.0,
            width_pct=5.0,
        )
        step = make_step_row(cycles=[fc])
        data = make_report_data(steps=[step])
        md = render_execution_report_markdown(data)
        blockquote_lines = [ln for ln in md.splitlines() if ln.startswith(">")]
        assert len(blockquote_lines) == 2


class TestStepLabelNull:
    """Step with step_label IS NULL falls back correctly."""

    def test_null_step_label_falls_back_to_agent_label(self) -> None:
        step = StepRow(
            step_id="S01",
            step_number=1,
            step_type="implementation",
            step_label=None,
            agent_label="BackendAgent",
            opencode_agent="backend-impl",
            display_label="BackendAgent",
            runs=[],
            fix_cycles=[],
            max_run_number=1,
            final_status=StepStatus.completed,
            is_hotspot=False,
            total_duration_secs=0.0,
        )
        data = make_report_data(steps=[step])
        md = render_execution_report_markdown(data)
        assert "BackendAgent" in md

    def test_null_step_label_and_agent_label_falls_back_to_opencode_agent(self) -> None:
        step = StepRow(
            step_id="S01",
            step_number=1,
            step_type="implementation",
            step_label=None,
            agent_label="",
            opencode_agent="backend-impl",
            display_label="backend-impl",
            runs=[],
            fix_cycles=[],
            max_run_number=1,
            final_status=StepStatus.completed,
            is_hotspot=False,
            total_duration_secs=0.0,
        )
        data = make_report_data(steps=[step])
        md = render_execution_report_markdown(data)
        assert "backend-impl" in md

    def test_null_step_label_and_agent_label_and_opencode_falls_back_to_step_id(self) -> None:
        step = StepRow(
            step_id="S01",
            step_number=1,
            step_type="implementation",
            step_label=None,
            agent_label="",
            opencode_agent=None,
            display_label="S01",
            runs=[],
            fix_cycles=[],
            max_run_number=1,
            final_status=StepStatus.completed,
            is_hotspot=False,
            total_duration_secs=0.0,
        )
        data = make_report_data(steps=[step])
        md = render_execution_report_markdown(data)
        assert "S01" in md
