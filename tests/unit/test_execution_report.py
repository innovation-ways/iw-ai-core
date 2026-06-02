"""Unit tests for execution_report — pure functions, no DB required.

Tests the markdown renderer and helper logic.
"""

from __future__ import annotations

from datetime import UTC, datetime

from orch.daemon.execution_report import (
    ExecutionReportData,
    FixCycleEntry,
    FixStatus,
    RetryHotspot,
    StepRow,
    StepRunSegment,
    _human_duration,
    _iso_or_dash,
    render_execution_report_markdown,
)


class DummyRunStatus:
    value = "completed"


class DummyStepStatus:
    value = "completed"


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_segment(
    run_number: int = 1,
    status: str = "completed",
    left_pct: float = 0.0,
    width_pct: float = 10.0,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> StepRunSegment:
    """Return make segment."""
    from orch.db.models import RunStatus

    if started_at is None:
        started_at = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
    if completed_at is None:
        completed_at = datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC)
    rs = RunStatus.completed if status == "completed" else RunStatus.failed
    return StepRunSegment(
        run_number=run_number,
        status=rs,
        started_at=started_at,
        completed_at=completed_at,
        duration_secs=60.0,
        error_message=None,
        report_file=None,
        report_content=None,
        is_final_attempt=(run_number == 1),
        gantt_class="completed" if status == "completed" else "failed",
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
    final_status: str = "completed",
) -> StepRow:
    """Return make step row."""
    from orch.db.models import StepStatus

    ss = StepStatus.completed if final_status == "completed" else StepStatus.failed
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
        final_status=ss,
        is_hotspot=max_run_number >= 2,
        total_duration_secs=60.0,
    )


def make_report_data(
    work_item_id: str = "F-00001",
    title: str = "Test Feature",
    verdict: str = "completed",
    steps: list[StepRow] | None = None,
    hotspots: list[RetryHotspot] | None = None,
) -> ExecutionReportData:
    """Return make report data."""
    return ExecutionReportData(
        project_id="test-proj",
        work_item_id=work_item_id,
        work_item_title=title,
        work_item_type="Feature",
        work_item_status=verdict,
        verdict=verdict,
        verdict_badge="✓ Completed" if verdict == "completed" else "✗ Failed",
        item_started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
        item_completed_at=datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC),
        total_duration_secs=3600.0,
        steps=steps or [make_step_row()],
        hotspots=hotspots or [],
        generated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# _human_duration
# ---------------------------------------------------------------------------


def test_human_duration_seconds() -> None:
    """Verifies that human duration seconds."""
    assert _human_duration(45.0) == "45s"


def test_human_duration_minutes() -> None:
    """Verifies that human duration minutes."""
    assert _human_duration(90.0) == "1m 30s"


def test_human_duration_hours() -> None:
    """Verifies that human duration hours."""
    assert _human_duration(3665.0) == "1h 1m"


# ---------------------------------------------------------------------------
# _iso_or_dash
# ---------------------------------------------------------------------------


def test_iso_or_dash_with_datetime() -> None:
    """Verifies that iso or dash with datetime."""
    dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
    result = _iso_or_dash(dt)
    assert "2025-01-15" in result
    assert "10:30:00" in result


def test_iso_or_dash_with_none() -> None:
    """Verifies that iso or dash with none."""
    assert _iso_or_dash(None) == "—"


# ---------------------------------------------------------------------------
# render_execution_report_markdown — happy path
# ---------------------------------------------------------------------------


def test_render_header_and_verdict() -> None:
    """Verifies that render header and verdict."""
    data = make_report_data(
        work_item_id="F-00056",
        title="Test Feature",
        verdict="completed",
    )
    md = render_execution_report_markdown(data)
    assert "# Execution Report: F-00056 — Test Feature" in md
    assert "**Verdict**: ✓ Completed" in md
    assert "**Type**: Feature" in md


def test_render_retry_hotspots_empty() -> None:
    """Verifies that render retry hotspots empty."""
    data = make_report_data(hotspots=[])
    md = render_execution_report_markdown(data)
    assert "## Retry Hotspots" in md
    assert "No retries — clean run." in md


def test_render_retry_hotspots_populated() -> None:
    """Verifies that render retry hotspots populated."""
    hotspots = [
        RetryHotspot(
            step_id="S03", display_label="Backend", retry_count=3, final_status="completed"
        ),
        RetryHotspot(step_id="S05", display_label="Tests", retry_count=2, final_status="failed"),
    ]
    data = make_report_data(hotspots=hotspots)
    md = render_execution_report_markdown(data)
    assert "## Retry Hotspots" in md
    assert "S03" in md
    assert "S05" in md
    assert "× 3" in md
    assert "× 2" in md


def test_render_step_timeline() -> None:
    """Verifies that render step timeline."""
    steps = [
        make_step_row(
            step_id="S01", step_number=1, display_label="Backend", final_status="completed"
        ),
        make_step_row(step_id="S02", step_number=2, display_label="Tests", final_status="failed"),
    ]
    data = make_report_data(steps=steps)
    md = render_execution_report_markdown(data)
    assert "## Step Timeline" in md
    assert "| S1 |" in md
    assert "| S2 |" in md


def test_render_fix_cycles_empty() -> None:
    """Verifies that render fix cycles empty."""
    steps = [make_step_row(cycles=[])]
    data = make_report_data(steps=steps)
    md = render_execution_report_markdown(data)
    assert "## Fix Cycles" in md
    assert "No fix cycles executed." in md


def test_render_fix_cycles_with_summary() -> None:
    """Verifies that render fix cycles with summary."""
    fc = FixCycleEntry(
        cycle_number=1,
        trigger_type="code_review",
        trigger_report="/path/to/trigger.md",
        fix_report="/path/to/fix.md",
        fix_summary="- Fixed SQL injection\n- Added validation",
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
    assert "## Fix Cycles" in md
    assert "Cycle 1 (code_review)" in md
    assert "> - Fixed SQL injection" in md
    assert "> - Added validation" in md
    assert "Trigger report:" in md
    assert "Fix report:" in md


def test_render_fix_cycles_without_summary() -> None:
    """Verifies that render fix cycles without summary."""
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


def test_render_footer() -> None:
    """Verifies that render footer."""
    data = make_report_data()
    md = render_execution_report_markdown(data)
    assert "---" in md
    assert "_Generated by iw item-report on" in md


def test_render_purity_no_io() -> None:
    """Identical data should produce identical markdown on repeated calls."""
    data = make_report_data()
    md1 = render_execution_report_markdown(data)
    md2 = render_execution_report_markdown(data)
    assert md1 == md2
