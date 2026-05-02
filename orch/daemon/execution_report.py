"""Execution report assembly and rendering for work items.

Pure functions: no DB writes in assemble/render, no caching.
"""

from __future__ import annotations

import json
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

from sqlalchemy import select

from orch.db.models import (
    FixCycle,
    FixStatus,
    Project,
    RunStatus,
    StepRun,
    StepStatus,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
)
from orch.self_assess import (
    SelfAssessFinding,
    SelfAssessmentData,
    SelfAssessParseError,
    findings_path_for,
    is_self_assess_step,
    parse_findings_json,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ExecutionReportResolutionError(RuntimeError):
    """Raised when report file path cannot be resolved."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepRunSegment:
    """One StepRun row, shaped for the Gantt/timeline."""

    run_number: int
    status: RunStatus
    started_at: datetime | None
    completed_at: datetime | None
    duration_secs: float | None
    error_message: str | None
    report_file: str | None
    report_content: str | None
    is_final_attempt: bool
    gantt_class: Literal["completed", "failed", "retry", "in_progress", "skipped"]
    left_pct: float
    width_pct: float


@dataclass(frozen=True)
class FixCycleEntry:
    """One FixCycle row with precomputed Gantt markers."""

    cycle_number: int
    trigger_type: str
    trigger_report: str | None
    fix_report: str | None
    fix_summary: str | None
    status: FixStatus
    started_at: datetime | None
    completed_at: datetime | None
    duration_secs: float | None
    left_pct: float
    width_pct: float


@dataclass(frozen=True)
class StepRow:
    """One WorkflowStep with its runs and fix cycles."""

    step_id: str
    step_number: int
    step_type: str
    step_label: str | None
    agent_label: str
    opencode_agent: str | None
    display_label: str
    runs: list[StepRunSegment]
    fix_cycles: list[FixCycleEntry]
    max_run_number: int
    final_status: StepStatus
    is_hotspot: bool
    total_duration_secs: float


@dataclass(frozen=True)
class RetryHotspot:
    """A step with multiple retry attempts."""

    step_id: str
    display_label: str
    retry_count: int
    final_status: str


@dataclass(frozen=True)
class ExecutionReportData:
    """Top-level execution report data."""

    project_id: str
    work_item_id: str
    work_item_title: str
    work_item_type: str
    work_item_status: str
    verdict: Literal["completed", "failed", "stalled", "in_progress", "not_started"]
    verdict_badge: str
    item_started_at: datetime | None
    item_completed_at: datetime | None
    total_duration_secs: float
    steps: list[StepRow]
    hotspots: list[RetryHotspot]
    generated_at: datetime
    self_assessment: SelfAssessmentData | None = field(default=None)


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _gantt_class_for_run(
    run: StepRunSegment, max_run_number: int
) -> Literal["completed", "failed", "retry", "in_progress", "skipped"]:
    if run.run_number < max_run_number:
        return "retry"
    if run.status == RunStatus.completed:
        return "completed"
    if run.status == RunStatus.failed:
        return "failed"
    if run.completed_at is None:
        return "in_progress"
    return "skipped"


def _final_status_for_step(step: WorkflowStep, runs: list[StepRun]) -> StepStatus:
    if not runs:
        return step.status
    latest = max(runs, key=lambda r: r.run_number)
    if latest.status == RunStatus.completed:
        return StepStatus.completed
    if latest.status == RunStatus.failed:
        return StepStatus.failed
    if latest.status == RunStatus.running:
        return StepStatus.in_progress
    return StepStatus.skipped


def _compute_gantt_pcts(
    started_at: datetime | None,
    completed_at: datetime | None,
    item_start: datetime,
    total_duration: float,
) -> tuple[float, float]:
    """Compute (left_pct, width_pct) for a Gantt segment.

    Clamps so left_pct in [0, 100], width_pct >= 0.5, left_pct + width_pct <= 100.
    """
    if total_duration <= 0 or started_at is None:
        return 0.0, 0.0

    now = datetime.now(UTC)
    end = completed_at if completed_at is not None else now
    end_ts = end.timestamp()
    start_ts = started_at.timestamp()
    item_start_ts = item_start.timestamp()

    left = (start_ts - item_start_ts) / total_duration * 100.0
    width = (end_ts - start_ts) / total_duration * 100.0

    left = max(0.0, min(100.0, left))
    width = max(0.5, width)
    if left + width > 100.0:
        width = 100.0 - left

    return round(left, 2), round(width, 2)


def _load_self_assessment(
    session: Session,
    steps: Sequence[WorkflowStep],
    _project_id: str,
    _work_item_id: str,
) -> SelfAssessmentData | None:
    """Load self-assessment findings for a work item, if available.

    Finds the ``self_assess`` step type, then locates its latest StepRun with
    a ``report_file``.  Uses ``findings_path_for`` to derive the JSON sidecar,
    reads the narrative from the report file, and parses findings.

    Returns None when:
      - no self_assess step exists
      - the step has not run or was skipped (no StepRun with a report_file, or
        final status is pending/skipped)
      - the findings JSON does not exist
      - the narrative file does not exist
    """
    # Find the self_assess step
    self_assess_steps = [s for s in steps if is_self_assess_step(s.step_type)]
    if not self_assess_steps:
        return None

    step = self_assess_steps[-1]  # use the last one if multiple (should be one)

    # Fetch latest StepRun for this step
    latest_run = session.execute(
        select(StepRun)
        .where(StepRun.step_id == step.id)
        .order_by(StepRun.run_number.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest_run is None:
        return None

    # Only render if the step actually ran (completed or failed)
    terminal_statuses = {RunStatus.completed, RunStatus.failed}
    if latest_run.status not in terminal_statuses:
        return None

    # Guard: report_file must exist
    if latest_run.report_file is None:
        return None

    report_path = Path(latest_run.report_file)

    # Read narrative from report file (optional)
    narrative_md: str | None = None
    if report_path.exists():
        with suppress(OSError):
            narrative_md = report_path.read_text(encoding="utf-8")

    # Derive findings JSON path
    findings_path = findings_path_for(report_path)

    if not findings_path.exists():
        # No findings JSON — return with narrative only
        return _build_self_assessment_data(narrative_md=narrative_md)

    # Parse findings JSON
    try:
        text = findings_path.read_text(encoding="utf-8")
        return parse_findings_json(text)
    except (OSError, json.JSONDecodeError, SelfAssessParseError) as exc:
        logger.warning("Could not parse self-assessment findings at %s: %s", findings_path, exc)
        # Return with empty findings but narrative intact
        return _build_self_assessment_data(narrative_md=narrative_md)


def _build_self_assessment_data(
    narrative_md: str | None = None,
) -> SelfAssessmentData:
    """Build a SelfAssessmentData with empty findings (parse-error sentinel)."""
    return SelfAssessmentData(
        narrative_md=narrative_md,
        findings=[],
        coverage_notes=None,
        bottom_line=None,
    )


def assemble_execution_report(
    session: Session, project_id: str, work_item_id: str
) -> ExecutionReportData:
    """Assemble execution report data from the DB for a single work item."""
    # Fetch WorkItem
    item = session.get(WorkItem, (project_id, work_item_id))
    if item is None:
        raise ValueError(f"Work item {work_item_id} not found in project {project_id}")

    # Fetch all steps for this item
    steps = (
        session.execute(
            select(WorkflowStep)
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == work_item_id,
            )
            .order_by(WorkflowStep.step_number)
        )
        .scalars()
        .all()
    )

    # Fetch all runs for these steps
    step_ids = [s.id for s in steps]
    runs_by_step: dict[int, list[StepRun]] = {sid: [] for sid in step_ids}
    if step_ids:
        runs = (
            session.execute(
                select(StepRun).where(StepRun.step_id.in_(step_ids)).order_by(StepRun.run_number)
            )
            .scalars()
            .all()
        )
        for r in runs:
            runs_by_step.setdefault(r.step_id, []).append(r)

    # Fetch all fix cycles for these steps
    cycles_by_step: dict[int, list[FixCycle]] = {sid: [] for sid in step_ids}
    if step_ids:
        cycles = (
            session.execute(select(FixCycle).where(FixCycle.step_id.in_(step_ids))).scalars().all()
        )
        for c in cycles:
            cycles_by_step.setdefault(c.step_id, []).append(c)

    # Compute item-level timing
    all_runs = [r for runs in runs_by_step.values() for r in runs]
    if all_runs:
        started_times = [r.started_at for r in all_runs if r.started_at is not None]
        completed_times = [r.completed_at for r in all_runs if r.completed_at is not None]
        item_started = min(started_times) if started_times else None
        item_completed: datetime | None = max(completed_times) if completed_times else None
        if item_started is None:
            total_duration = 0.0
        else:
            end_for_calc = item_completed if item_completed else datetime.now(UTC)
            total_duration = (end_for_calc - item_started).total_seconds()
    else:
        item_started = None
        item_completed = None
        total_duration = 0.0

    # Compute verdict
    verdict_map: dict[
        WorkItemStatus, Literal["completed", "failed", "stalled", "in_progress", "not_started"]
    ] = {
        WorkItemStatus.completed: "completed",
        WorkItemStatus.failed: "failed",
        WorkItemStatus.paused: "stalled",
        WorkItemStatus.in_progress: "in_progress",
        WorkItemStatus.draft: "not_started",
        WorkItemStatus.approved: "not_started",
        WorkItemStatus.cancelled: "failed",
    }
    verdict = verdict_map.get(item.status, "not_started")
    if not all_runs and item.status in (WorkItemStatus.draft, WorkItemStatus.approved):
        verdict = "not_started"

    badge_map = {
        "completed": "✓ Completed",
        "failed": "✗ Failed",
        "stalled": "⚠ Stalled",
        "in_progress": "⟳ In Progress",
        "not_started": "○ Not Started",
    }
    verdict_badge = badge_map.get(verdict, verdict)

    # Build step rows
    step_rows: list[StepRow] = []
    hotspots: list[RetryHotspot] = []

    for step in steps:
        runs = runs_by_step.get(step.id, [])
        cycles = cycles_by_step.get(step.id, [])
        max_run_number = max((r.run_number for r in runs), default=0)

        # Final status
        final_status = _final_status_for_step(step, runs)

        # display_label fallback: step_label -> agent_label -> opencode_agent -> step_id
        display_label = step.step_label or step.agent_label
        if display_label is None:
            display_label = step.opencode_agent or step.step_id

        # Compute total_duration for this step
        if runs:
            run_starts = [r.started_at for r in runs if r.started_at is not None]
            run_ends = [r.completed_at for r in runs if r.completed_at is not None]
            if run_starts:
                step_start = min(run_starts)
                step_end = max(run_ends) if run_ends else datetime.now(UTC)
                step_duration = (step_end - step_start).total_seconds()
            else:
                step_duration = 0.0
        else:
            step_duration = 0.0

        # Build run segments with Gantt data
        item_start_for_calc = item_started if item_started else datetime.now(UTC)
        run_segments: list[StepRunSegment] = []
        for r in runs:
            is_final = r.run_number == max_run_number
            status: RunStatus = r.status
            # duration_secs from DB
            dur = r.duration_secs
            # completed_at handling
            comp_at = r.completed_at
            if comp_at is None and r.started_at is not None:
                comp_at = datetime.now(UTC)

            left_pct, width_pct = _compute_gantt_pcts(
                r.started_at, comp_at, item_start_for_calc, total_duration
            )

            gantt = _gantt_class_for_run(
                StepRunSegment(
                    run_number=r.run_number,
                    status=status,
                    started_at=r.started_at,
                    completed_at=comp_at,
                    duration_secs=dur,
                    error_message=r.error_message,
                    report_file=r.report_file,
                    report_content=None,
                    is_final_attempt=is_final,
                    gantt_class="completed",
                    left_pct=0.0,
                    width_pct=0.0,
                ),
                max_run_number,
            )

            run_segments.append(
                StepRunSegment(
                    run_number=r.run_number,
                    status=status,
                    started_at=r.started_at,
                    completed_at=comp_at,
                    duration_secs=dur,
                    error_message=r.error_message,
                    report_file=r.report_file,
                    report_content=None,
                    is_final_attempt=is_final,
                    gantt_class=gantt,
                    left_pct=left_pct,
                    width_pct=width_pct,
                )
            )

        # Build fix cycle entries with Gantt markers
        cycle_entries: list[FixCycleEntry] = []
        for c in sorted(cycles, key=lambda x: x.cycle_number):
            left_pct, width_pct = _compute_gantt_pcts(
                c.started_at, c.completed_at, item_start_for_calc, total_duration
            )
            dur_secs: float | None = None
            if c.started_at is not None and c.completed_at is not None:
                dur_secs = (c.completed_at - c.started_at).total_seconds()
            cycle_entries.append(
                FixCycleEntry(
                    cycle_number=c.cycle_number,
                    trigger_type=c.trigger_type.value,
                    trigger_report=c.trigger_report,
                    fix_report=c.fix_report,
                    fix_summary=c.fix_summary,
                    status=c.status,
                    started_at=c.started_at,
                    completed_at=c.completed_at,
                    duration_secs=dur_secs,
                    left_pct=left_pct,
                    width_pct=width_pct,
                )
            )

        is_hotspot = max_run_number >= 2

        step_rows.append(
            StepRow(
                step_id=step.step_id,
                step_number=step.step_number,
                step_type=step.step_type.value,
                step_label=step.step_label,
                agent_label=step.agent_label,
                opencode_agent=step.opencode_agent,
                display_label=display_label,
                runs=run_segments,
                fix_cycles=cycle_entries,
                max_run_number=max_run_number,
                final_status=final_status,
                is_hotspot=is_hotspot,
                total_duration_secs=step_duration,
            )
        )

        if is_hotspot:
            hotspots.append(
                RetryHotspot(
                    step_id=step.step_id,
                    display_label=display_label,
                    retry_count=max_run_number,
                    final_status=final_status.value,
                )
            )

    # Sort hotspots: retry_count desc, then step_number asc
    hotspots.sort(key=lambda h: (-h.retry_count, h.step_id))

    # ── Self-Assessment ─────────────────────────────────────────────────────
    self_assessment: SelfAssessmentData | None = None
    try:
        self_assessment = _load_self_assessment(session, steps, project_id, work_item_id)
    except Exception as exc:
        logger.exception(
            "Failed to load self-assessment data for %s/%s: %s", project_id, work_item_id, exc
        )

    return ExecutionReportData(
        project_id=project_id,
        work_item_id=work_item_id,
        work_item_title=item.title,
        work_item_type=item.type.value,
        work_item_status=item.status.value,
        verdict=verdict,
        verdict_badge=verdict_badge,
        item_started_at=item_started,
        item_completed_at=item_completed,
        total_duration_secs=round(total_duration, 2),
        steps=step_rows,
        hotspots=hotspots,
        generated_at=datetime.now(UTC),
        self_assessment=self_assessment,
    )


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------


def _human_duration(secs: float) -> str:
    """Format a duration in seconds as a human-readable string."""
    if secs < 60:
        return f"{secs:.0f}s"
    if secs < 3600:
        mins = int(secs // 60)
        rem = int(secs % 60)
        return f"{mins}m {rem}s"
    hours = int(secs // 3600)
    mins = int((secs % 3600) // 60)
    return f"{hours}h {mins}m"


def _iso_or_dash(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.isoformat()


def render_execution_report_markdown(data: ExecutionReportData) -> str:
    """Render ExecutionReportData to a markdown string."""
    lines: list[str] = []

    # Section 1: Header + verdict
    lines.append(f"# Execution Report: {data.work_item_id} — {data.work_item_title}")
    lines.append("")
    lines.append(
        f"**Verdict**: {data.verdict_badge}  \n"
        f"**Type**: {data.work_item_type}  \n"
        f"**Started**: {_iso_or_dash(data.item_started_at)}  \n"
        f"**Completed**: {_iso_or_dash(data.item_completed_at)}  \n"
        f"**Total wall-clock**: {_human_duration(data.total_duration_secs)}  \n"
        f"**Generated**: {data.generated_at.isoformat()}"
    )
    lines.append("")

    # Section 2: Retry hotspots
    lines.append("## Retry Hotspots")
    if not data.hotspots:
        lines.append("No retries — clean run.")
    else:
        for h in data.hotspots:
            lines.append(
                f"- **S{h.step_id[1:]}** `{h.display_label}` × {h.retry_count} "
                f"(final: {h.final_status})"
            )
    lines.append("")

    # Section 3: Step timeline
    lines.append("## Step Timeline")
    lines.append("| Step | Label | Attempts | Final Status | Duration |")
    lines.append("|------|-------|----------|---------------|----------|")
    for s in data.steps:
        attempts = s.max_run_number if s.max_run_number > 0 else "—"
        dur = _human_duration(s.total_duration_secs) if s.total_duration_secs > 0 else "—"
        lines.append(
            f"| S{s.step_number} | {s.display_label} | {attempts} | "
            f"{s.final_status.value} | {dur} |"
        )
    lines.append("")

    # Section 4: Fix cycle details
    lines.append("## Fix Cycles")
    has_any_cycle = any(s.fix_cycles for s in data.steps)
    if not has_any_cycle:
        lines.append("No fix cycles executed.")
    else:
        for s in data.steps:
            if not s.fix_cycles:
                continue
            lines.append(f"### S{s.step_number} {s.display_label}")
            for fc in s.fix_cycles:
                dur_str = f"{fc.duration_secs:.0f}s" if fc.duration_secs is not None else "—"
                lines.append(
                    f"#### Cycle {fc.cycle_number} ({fc.trigger_type}) — "
                    f"{fc.status.value}, {dur_str}"
                )
                if fc.fix_summary:
                    # Multi-line blockquote for multi-bullet summaries
                    for ln in fc.fix_summary.splitlines():
                        lines.append(f"> {ln}")
                else:
                    lines.append("> _no fix summary captured (pre-F-00056)_")
                if fc.trigger_report:
                    lines.append(f"Trigger report: {fc.trigger_report}")
                if fc.fix_report:
                    lines.append(f"Fix report: {fc.fix_report}")
                lines.append("")
            lines.append("")

    # Section 5: Self-Assessment
    if data.self_assessment is not None:
        lines.append("## Self-Assessment")
        sa = data.self_assessment
        if sa.bottom_line:
            lines.append(f"\n_{sa.bottom_line}_\n")
        if sa.coverage_notes:
            lines.append(f"_Coverage: {sa.coverage_notes}_\n")

        # Group findings
        core_findings = [f for f in sa.findings if f.target == "iw-ai-core"]
        project_findings = [f for f in sa.findings if f.target == "project"]

        # Sort by severity
        sev_order = {"HIGH": 0, "MED": 1, "LOW": 2}

        def sort_key(f: SelfAssessFinding) -> int:
            return sev_order.get(f.severity, 3)

        if core_findings:
            lines.append("### Suggestions for iw-ai-core")
            for f in sorted(core_findings, key=sort_key):
                lines.append(f"- **[{f.severity}]** {f.title}")
                lines.append(f"  - Recommendation: {f.recommendation}")
                lines.append(f"  ```\n  {f.paste_prompt}\n  ```")
            lines.append("")

        if project_findings:
            lines.append(f"### Suggestions for {data.project_id}")
            for f in sorted(project_findings, key=sort_key):
                lines.append(f"- **[{f.severity}]** {f.title}")
                lines.append(f"  - Recommendation: {f.recommendation}")
                lines.append(f"  ```\n  {f.paste_prompt}\n  ```")
            lines.append("")

        if sa.findings and not core_findings and not project_findings:
            lines.append("Self-assessment ran but no findings were captured.")

        if not sa.findings:
            lines.append("Self-assessment ran but no findings were captured.")

        # Narrative (if present)
        if sa.narrative_md:
            lines.append("\n### Full Narrative\n")
            lines.append("```markdown")
            lines.append(sa.narrative_md)
            lines.append("```")

        lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"_Generated by iw item-report on {data.generated_at.isoformat()}._")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_report_path(session: Session, project_id: str, work_item_id: str) -> Path:
    """Resolve the report file path for a work item.

    Looks in active dir first, then archive dir.
    Raises ExecutionReportResolutionError if project not found or neither dir exists.
    """
    project = session.get(Project, project_id)
    if project is None:
        raise ExecutionReportResolutionError(f"Project {project_id} not found")

    repo_root = Path(project.repo_root)
    active_dir = repo_root / "ai-dev" / "active" / work_item_id
    archive_dir = repo_root / "ai-dev" / "archive" / work_item_id

    if active_dir.exists():
        return active_dir / f"{work_item_id}_execution_report.md"
    if archive_dir.exists():
        return archive_dir / f"{work_item_id}_execution_report.md"

    raise ExecutionReportResolutionError(
        f"Neither {active_dir} nor {archive_dir} exists for work item {work_item_id}"
    )


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def write_execution_report(session: Session, project_id: str, work_item_id: str) -> Path:
    """Assemble report, render markdown, and write to disk.

    Returns the path written.
    Raises ExecutionReportResolutionError on path resolution failure.
    """
    data = assemble_execution_report(session, project_id, work_item_id)
    markdown = render_execution_report_markdown(data)
    path = resolve_report_path(session, project_id, work_item_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path
