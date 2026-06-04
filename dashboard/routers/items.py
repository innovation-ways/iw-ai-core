"""Work item detail page and htmx tab fragment routes."""

from __future__ import annotations

import json
import mimetypes
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple, TypedDict

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from markupsafe import Markup
from pygments import highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers.diff import DiffLexer
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.utils.markdown import render_markdown
from orch.daemon.execution_report import assemble_execution_report
from orch.db.models import (
    AgentRuntimeOption,
    Batch,
    BatchItem,
    BatchItemStatus,
    DaemonEvent,
    EvidencePhase,
    FixCycle,
    Project,
    RegressionClassification,
    RunStatus,
    StepRun,
    StepStatus,
    WorkflowStep,
    WorkItem,
    WorkItemEvidence,
)
from orch.regression_link_service import Candidate  # F-00090: type annotation for _top_suggestion

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# TypedDict helpers (used in htmx fragment routes)
# ---------------------------------------------------------------------------


class SessionLogSegment(TypedDict, total=False):
    """A rendered log segment produced by session_reader.read_session_content."""

    type: str  # "assistant" | "tool_call" | "tool_result" | "thinking"
    #             | "compaction" | "error" | "log"
    text: str
    collapsible: bool


router = APIRouter(prefix="/project/{project_id}")


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class StepDetail:
    """Full step info for the item overview tab."""

    step_id: str
    agent_label: str
    step_type: str
    status: str
    duration_secs: float | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    run_count: int
    step_label: str | None = None
    description: str | None = None
    report_content: str | None = None
    is_synthetic: bool = False
    fix_cycle_count: int = 0
    restartable: bool = False
    # F-00081: resolved runtime option id (from step_runs → step override → item override)
    runtime_option_id: int | None = None
    # F-00081: step-level override (explicitly set on workflow_step row)
    step_runtime_option_id: int | None = None
    # CR-00056 S06: True if any StepRun for this step has prompt_text or fix_prompt_text
    has_prompt: bool = False
    # I-00101: scope-violation paths from the latest escalated FixCycle on this step
    scope_violations: list[str] | None = None

    # CR-00066: context window usage tracking
    context_tokens_peak: int | None = None
    context_tokens_last: int | None = None
    context_window_tokens: int | None = None
    max_output_tokens: int | None = None
    # I-00105 S05: effective-budget % precomputed via compute_effective_context_pct
    # (may be None when effective_budget is non-positive; bar width clamps to 100%)
    context_effective_pct: float | None = None


@dataclass
class ReportSection:
    """A rendered report for a single step, used in the reports tab."""

    step_id: str
    agent_label: str
    step_type: str
    status: str
    run_count: int
    report_html: str


@dataclass
class RunLog:
    """A single step_run entry for the logs tab."""

    run_number: int
    status: str
    duration_secs: float | None
    is_running: bool
    log_content: str | None
    log_modified: str | None = None


@dataclass
class LogSection:
    """All runs for a single workflow step, for the logs tab."""

    step_id: str
    agent_label: str
    status: str
    db_step_id: int | None
    runs: list[RunLog]
    static_content: str | None = None


def _detect_file_type(name: str) -> str:
    """Map a filename to a viewer content type."""
    name_lower = name.lower()
    if name_lower.endswith(".md"):
        return "markdown"
    image_exts = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
    if any(name_lower.endswith(e) for e in image_exts):
        return "image"
    text_exts = (
        ".txt",
        ".log",
        ".json",
        ".yaml",
        ".yml",
        ".sh",
        ".py",
        ".toml",
        ".cfg",
        ".ini",
        ".sql",
        ".html",
        ".css",
        ".js",
        ".ts",
        ".xml",
        ".env",
    )
    if any(name_lower.endswith(e) for e in text_exts):
        return "text"
    return "binary"


def _resolve_artifact_root(
    item: WorkItem, project: Project, worktree_path: str | None
) -> Path | None:
    """Return the first existing candidate path for the artifact directory.

    Worktree is preferred; falls back to repo_root. Returns None if neither
    exists or if item.design_doc_path is None.
    """
    if item.design_doc_path is None:
        return None
    rel_dir = Path(item.design_doc_path).parent
    candidates: list[Path] = []
    if worktree_path:
        candidates.append(Path(worktree_path) / rel_dir)
    candidates.append(Path(project.repo_root) / rel_dir)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


@dataclass
class EvidenceFile:
    """A single screenshot/snapshot in the evidences browser."""

    filename: str
    phase: str  # "pre" or "post"
    abs_path: str  # populated from FS only when not in DB
    size_bytes: int
    content: bytes | None = None  # populated from DB
    content_type: str | None = None  # populated from DB


@dataclass
class ItemMetrics:
    """Computed metrics for the item detail header."""

    total_duration_secs: float | None
    fix_cycles_count: int
    steps_completed: int
    steps_total: int


@dataclass
class FixCycleDetail:
    """A single fix cycle record for the fix-cycles tab."""

    id: int
    db_step_id: int
    step_id: str
    agent_label: str
    cycle_number: int
    trigger_type: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_secs: float | None
    log_content: str | None
    log_modified: str | None
    is_running: bool


@dataclass
class CascadeNode:
    """A single cascade/replay event in the causality tree."""

    timestamp: datetime
    trigger_step_id: str
    cycle_id: int | None
    reset_step_ids: list[str]
    event_type: str  # 'cascaded_replay_after_fix' or 'review_replay_after_fix'
    changed_files: list[str] = field(default_factory=list)  # review events only
    review_reset_step_ids: list[str] = field(default_factory=list)  # review events only
    children: list[CascadeNode] = field(default_factory=list)


@dataclass
class ThrashingAlert:
    """Details from a cascade_thrashing_detected event."""

    trigger_step_id: str
    cascade_count: int
    recommendation: str
    created_at: datetime


class CascadeHistory(NamedTuple):
    """Cascade-related daemon events for a work item, structured for template rendering."""

    cascade_event_count: int
    fix_cycle_count: int
    replay_wall_clock_minutes: float | None
    tree: list[CascadeNode]  # top-level cascade events
    thrashing: ThrashingAlert | None


def _now_iso() -> str:
    """Return current UTC time as ISO string for PDF generation timestamps."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# Duration aggregation helpers
# ---------------------------------------------------------------------------


def _aggregate_step_spans(
    db: Session, step_db_ids: list[int]
) -> dict[int, tuple[datetime | None, datetime | None]]:
    """Aggregate step spans from append-only step_runs and fix_cycles tables.

    I-00034: WorkflowStep.started_at/completed_at reflect only the LAST iteration
    (daemon resets them on retry/fix-cycle). Aggregate from append-only step_runs ∪ fix_cycles.
    Returns dict mapping step_id -> (earliest_started, latest_completed).
    Only steps with at least one completed row are included.
    """
    from sqlalchemy import func

    spans: dict[int, tuple[datetime | None, datetime | None]] = {}

    from sqlalchemy import case

    run_rows = db.execute(
        select(
            StepRun.step_id,
            func.min(StepRun.started_at).label("earliest"),
            case(
                (func.count(StepRun.completed_at) < func.count(StepRun.id), None),
                else_=func.max(StepRun.completed_at),
            ).label("latest"),
        )
        .where(StepRun.step_id.in_(step_db_ids))
        .group_by(StepRun.step_id)
    ).all()
    for row in run_rows:
        spans[row.step_id] = (row.earliest, row.latest)

    cycle_rows = db.execute(
        select(
            FixCycle.step_id,
            func.min(FixCycle.started_at).label("earliest"),
            case(
                (func.count(FixCycle.completed_at) < func.count(FixCycle.id), None),
                else_=func.max(FixCycle.completed_at),
            ).label("latest"),
        )
        .where(FixCycle.step_id.in_(step_db_ids))
        .group_by(FixCycle.step_id)
    ).all()
    for row in cycle_rows:
        existing = spans.get(row.step_id)
        if existing is None:
            spans[row.step_id] = (row.earliest, row.latest)
        else:
            earliest_candidates = [v for v in (existing[0], row.earliest) if v is not None]
            earliest = min(earliest_candidates) if earliest_candidates else None
            # If either side still has an incomplete aggregate (None from the CASE
            # above), the step is not fully finished - the combined latest is None.
            if existing[1] is None or row.latest is None:
                latest = None
            else:
                latest = max(existing[1], row.latest)
            spans[row.step_id] = (earliest, latest)

    return spans


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _get_project_or_404(project_id: str, db: Session) -> Project:
    """Fetch a Project by id or raise HTTP 404.

    Args:
        project_id: Identifier of the project to look up.
        db: Active database session.

    Returns:
        The matching Project row.

    Raises:
        HTTPException: 404 when no project with the given id exists.
    """
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")
    return project


def _get_item_or_404(project_id: str, item_id: str, db: Session) -> WorkItem:
    """Fetch a WorkItem by (project_id, item_id) or raise HTTP 404.

    Args:
        project_id: Project the item belongs to.
        item_id: Identifier of the work item.
        db: Active database session.

    Returns:
        The matching WorkItem row.

    Raises:
        HTTPException: 404 when no work item with the given ids exists.
    """
    item = db.scalar(
        select(WorkItem).where(
            WorkItem.project_id == project_id,
            WorkItem.id == item_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail=f"Work item {item_id!r} not found")
    return item


def _read_report_file(report_file: str | None, repo_root: str | None) -> str | None:
    """Read report markdown from disk when DB content is not available."""
    if report_file is None or repo_root is None:
        return None
    path = Path(repo_root) / report_file
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _get_steps(
    project_id: str, item_id: str, db: Session, project: Project | None = None
) -> list[StepDetail]:
    """Load all workflow steps for a work item, enriched with run/fix-cycle data.

    Builds the full list used by the overview and logs tabs: a synthetic S00
    setup step, all real workflow steps ordered by step_number, and a synthetic
    MERGE step appended at the end.

    Args:
        project_id: Project owning the work item.
        item_id: Work item to load steps for.
        db: Active database session.
        project: Optional pre-fetched Project row; used for disk-based report
            fallback. When None, report fallback is skipped.

    Returns:
        Ordered list of StepDetail instances including synthetic setup and merge steps.
    """
    from sqlalchemy import func

    bi = _get_batch_item(project_id, item_id, db)
    repo_root = project.repo_root if project else None
    workflow_steps = list(
        db.scalars(
            select(WorkflowStep)
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
            .order_by(WorkflowStep.step_number)
        ).all()
    )
    step_db_ids = [s.id for s in workflow_steps]
    fix_cycle_counts: dict[int, int] = {}
    if step_db_ids:
        rows = db.execute(
            select(FixCycle.step_id, func.count(FixCycle.id).label("cnt"))
            .where(FixCycle.step_id.in_(step_db_ids))
            .group_by(FixCycle.step_id)
        ).all()
        fix_cycle_counts = {row.step_id: row.cnt for row in rows}

    # CR-00066: build id→(context_window_tokens, max_output_tokens) lookup from AgentRuntimeOption
    runtime_opt_data: dict[int, tuple[int, int]] = {}
    opt_rows = db.execute(
        select(
            AgentRuntimeOption.id,
            AgentRuntimeOption.context_window_tokens,
            AgentRuntimeOption.max_output_tokens,
        ).where(AgentRuntimeOption.enabled.is_(True))
    ).all()
    for row in opt_rows:
        if row.context_window_tokens is not None:
            runtime_opt_data[row.id] = (row.context_window_tokens, row.max_output_tokens)

    step_spans = _aggregate_step_spans(db, step_db_ids)

    # F-00081: runtime option id from last run (most recent step_runs row per step)
    last_run_option_map: dict[int, int] = {}
    last_run_sub = (
        select(
            StepRun.step_id,
            StepRun.agent_runtime_option_id,
            func.row_number()
            .over(
                partition_by=StepRun.step_id,
                order_by=StepRun.run_number.desc(),
            )
            .label("rn"),
        )
        .where(StepRun.step_id.in_(step_db_ids))
        .subquery()
    )
    run_option_rows = db.execute(
        select(last_run_sub.c.step_id, last_run_sub.c.agent_runtime_option_id).where(
            last_run_sub.c.rn == 1
        )
    ).all()
    for row in run_option_rows:
        last_run_option_map[row.step_id] = row.agent_runtime_option_id

    last_run_map: dict[int, StepRun] = {}
    run_count_map: dict[int, int] = {}
    has_prompt_map: dict[int, bool] = {}
    if step_db_ids:
        last_run_sub2 = (
            select(
                StepRun.step_id,
                StepRun.id.label("run_id"),
                StepRun.error_message,
                StepRun.prompt_text,
                StepRun.fix_prompt_text,
                StepRun.context_tokens_peak,
                StepRun.context_tokens_last,
                func.row_number()
                .over(
                    partition_by=StepRun.step_id,
                    order_by=StepRun.run_number.desc(),
                )
                .label("rn"),
                func.count(StepRun.id).over(partition_by=StepRun.step_id).label("rc"),
            )
            .where(StepRun.step_id.in_(step_db_ids))
            .subquery()
        )
        bulk_rows = db.execute(
            select(
                last_run_sub2.c.step_id,
                last_run_sub2.c.run_id,
                last_run_sub2.c.error_message,
                last_run_sub2.c.prompt_text,
                last_run_sub2.c.fix_prompt_text,
                last_run_sub2.c.context_tokens_peak,
                last_run_sub2.c.context_tokens_last,
                last_run_sub2.c.rc,
            ).where(last_run_sub2.c.rn == 1)
        ).all()
        for row in bulk_rows:
            run = StepRun(
                id=row.run_id,
                step_id=row.step_id,
                error_message=row.error_message,
                run_number=0,
                status=None,
            )
            last_run_map[row.step_id] = run
            run_count_map[row.step_id] = row.rc
            has_prompt_map[row.step_id] = bool(
                row.prompt_text is not None or row.fix_prompt_text is not None
            )
            # CR-00066: context tokens from the last run row
            run.context_tokens_peak = row.context_tokens_peak
            run.context_tokens_last = row.context_tokens_last

    # F-00081: item-level runtime override
    item = db.scalar(
        select(WorkItem).where(
            WorkItem.project_id == project_id,
            WorkItem.id == item_id,
        )
    )
    item_runtime_option_id = item.agent_runtime_option_id if item else None

    result: list[StepDetail] = [_synthetic_setup_step(bi, [s.status.value for s in workflow_steps])]

    # I-00101: bulk-fetch scope_violations for all needs_fix steps (single query, N+1-safe)
    needs_fix_ids = [s.id for s in workflow_steps if s.status == StepStatus.needs_fix]
    scope_violations_map: dict[int, list[str]] = {}
    if needs_fix_ids:
        from orch.daemon.scope_amendment import latest_scope_violation

        for step_db_id in needs_fix_ids:
            violations = latest_scope_violation(db, step_db_id)
            if violations:
                scope_violations_map[step_db_id] = violations

    for step in workflow_steps:
        last_run = last_run_map.get(step.id)
        error_msg = last_run.error_message if last_run else None
        run_count = run_count_map.get(step.id, 0)

        earliest_started_at, latest_completed_at = step_spans.get(step.id, (None, None))
        if earliest_started_at is not None and latest_completed_at is not None:
            dur = (latest_completed_at - earliest_started_at).total_seconds()
        else:
            dur = None

        report = step.report_content or _read_report_file(step.report_file, repo_root)

        # F-00081: runtime_option_id resolution:
        # - step override (workflow_steps.agent_runtime_option_id)
        # - item override (WorkItem.agent_runtime_option_id)
        run_opt_id = last_run_option_map.get(step.id)
        step_opt_id = step.agent_runtime_option_id  # explicit step-level override

        # CR-00066: resolve context_window_tokens + max_output_tokens from runtime option
        resolved_opt_id = (
            run_opt_id if run_opt_id is not None else (step_opt_id or item_runtime_option_id)
        )
        ctx_win = None
        max_out = None
        opt_data = runtime_opt_data.get(resolved_opt_id) if resolved_opt_id else None
        if opt_data:
            ctx_win, max_out = opt_data

        # I-00105 S05: precompute effective-budget percentage via compute_effective_context_pct
        context_effective_pct: float | None = None
        ctx_peak = last_run.context_tokens_peak if last_run else None
        if ctx_peak is not None and ctx_win is not None and ctx_win > 0:
            from orch.chat.context_usage import compute_effective_context_pct

            context_effective_pct = compute_effective_context_pct(ctx_peak, ctx_win, max_out)

        result.append(
            StepDetail(
                step_id=step.step_id,
                agent_label=step.agent_label,
                step_type=step.step_type.value,
                status=step.status.value,
                duration_secs=dur,
                started_at=earliest_started_at,
                completed_at=latest_completed_at,
                error_message=error_msg,
                run_count=run_count,
                step_label=step.step_label,
                description=step.description,
                report_content=report,
                fix_cycle_count=fix_cycle_counts.get(step.id, 0),
                runtime_option_id=resolved_opt_id,
                step_runtime_option_id=step_opt_id,
                has_prompt=has_prompt_map.get(step.id, False),
                scope_violations=scope_violations_map.get(step.id),
                # CR-00066: context window data
                context_tokens_peak=ctx_peak,
                context_tokens_last=last_run.context_tokens_last if last_run else None,
                context_window_tokens=ctx_win,
                max_output_tokens=max_out,
                context_effective_pct=context_effective_pct,
            )
        )
    result.append(_synthetic_merge_step(bi))
    return result


def _get_metrics(
    project_id: str, item_id: str, steps: list[StepDetail], db: Session
) -> ItemMetrics:
    """Compute aggregate metrics for the item detail header.

    Args:
        project_id: Project owning the work item.
        item_id: Work item to compute metrics for.
        steps: Pre-loaded list of StepDetail instances (from _get_steps).
        db: Active database session.

    Returns:
        ItemMetrics with total duration, fix cycle count, and step completion counts.
    """
    # Total duration: from first step start to last step end
    started_ats = [s.started_at for s in steps if s.started_at]
    completed_ats = [s.completed_at for s in steps if s.completed_at]
    total_dur: float | None = None
    if started_ats and completed_ats:
        total_dur = (max(completed_ats) - min(started_ats)).total_seconds()

    # Fix cycles: sum across all steps
    step_db_ids = list(
        db.scalars(
            select(WorkflowStep.id).where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
        ).all()
    )
    fix_count = 0
    if step_db_ids:
        fix_count = len(
            list(db.scalars(select(FixCycle.id).where(FixCycle.step_id.in_(step_db_ids))).all())
        )

    steps_completed = sum(1 for s in steps if s.status == "completed")
    return ItemMetrics(
        total_duration_secs=total_dur,
        fix_cycles_count=fix_count,
        steps_completed=steps_completed,
        steps_total=len(steps),
    )


def _get_batch_ref(project_id: str, item_id: str, db: Session) -> str | None:
    """Return the batch_id for the most recent BatchItem associated with an item.

    Args:
        project_id: Project owning the work item.
        item_id: Work item to look up.
        db: Active database session.

    Returns:
        The batch_id string, or None when no BatchItem exists.
    """
    bi = db.scalar(
        select(BatchItem)
        .where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
        )
        .order_by(BatchItem.id.desc())
    )
    return bi.batch_id if bi else None


def _get_batch_status(project_id: str, batch_id: str | None, db: Session) -> str | None:
    """Return the status string of a batch, or None if not found."""
    if not batch_id:
        return None
    batch = db.get(Batch, (project_id, batch_id))
    if batch is None:
        return None
    # Handle both enum and plain-str status (graceful for testcontainer variance)
    status = batch.status
    if hasattr(status, "value"):
        return str(status.value)
    return str(status)


def _get_batch_item_error(project_id: str, item_id: str, db: Session) -> str | None:
    """Return the batch_item notes if the item failed at setup (no step runs)."""
    bi = db.scalar(
        select(BatchItem)
        .where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
            BatchItem.status == BatchItemStatus.failed,
        )
        .order_by(BatchItem.id.desc())
    )
    if bi and bi.notes:
        return bi.notes
    return None


def _get_batch_item(project_id: str, item_id: str, db: Session) -> BatchItem | None:
    """Return the most recent BatchItem for a work item, or None if not found.

    Args:
        project_id: Project the batch item belongs to.
        item_id: Work item identifier to look up.
        db: Active database session.

    Returns:
        The most recent BatchItem row, or None.
    """
    return db.scalar(
        select(BatchItem)
        .where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
        )
        .order_by(BatchItem.id.desc())
    )


def _setup_status(bi: BatchItem | None) -> str:
    """Derive the display status string for the synthetic worktree-setup step.

    Args:
        bi: The most recent BatchItem for the work item, or None.

    Returns:
        One of ``"completed"``, ``"in_progress"``, ``"failed"``, or ``"pending"``.
    """
    if bi is None:
        return "pending"
    if bi.worktree_info:
        return "completed"
    if bi.status == BatchItemStatus.setting_up:
        return "in_progress"
    if bi.status == BatchItemStatus.failed:
        return "failed"
    return "pending"


def _merge_status(bi: BatchItem | None) -> str:
    """Derive the display status string for the synthetic squash-merge step.

    Args:
        bi: The most recent BatchItem for the work item, or None.

    Returns:
        One of ``"awaiting_approval"``, ``"completed"``, ``"in_progress"``,
        ``"failed"``, ``"merge_failed"``, or ``"pending"``.
    """
    if bi is None:
        return "pending"
    if bi.status == BatchItemStatus.awaiting_merge_approval:
        return "awaiting_approval"
    if bi.merged_at is not None:
        return "completed"
    if not bi.worktree_info:
        return "pending"
    if bi.status in (BatchItemStatus.merging, BatchItemStatus.completed):
        return "in_progress"
    if bi.status == BatchItemStatus.failed:
        return "failed"
    recoverable_merge_statuses = {
        BatchItemStatus.merge_failed,
        BatchItemStatus.migration_invalid,
        BatchItemStatus.migration_rebase_failed,
    }
    if bi.status in recoverable_merge_statuses:
        return "merge_failed"
    return "pending"


def _synthetic_setup_step(
    bi: BatchItem | None, step_statuses: list[str] | None = None
) -> StepDetail:
    """Build a synthetic StepDetail representing worktree setup (S00).

    Args:
        bi: The most recent BatchItem for the work item, or None.
        step_statuses: Optional list of real step status strings used to
            determine whether the setup step is eligible for restart.

    Returns:
        A StepDetail with step_id ``"S00"`` and ``is_synthetic=True``.
    """
    status = _setup_status(bi)
    dur: float | None = None
    if bi and bi.worktree_info and bi.started_at:
        from datetime import datetime

        created_raw = (
            bi.worktree_info.get("created_at") if isinstance(bi.worktree_info, dict) else None
        )
        if created_raw:
            try:
                created = datetime.fromisoformat(created_raw)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                started = bi.started_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=UTC)
                dur = (created - started).total_seconds()
                if dur < 0:
                    dur = None
            except ValueError:
                pass

    restartable = False
    if (
        step_statuses is not None
        and bi is not None
        and bi.status in (BatchItemStatus.setup_failed, BatchItemStatus.failed)
        and (len(step_statuses) == 0 or all(s == "pending" for s in step_statuses))
    ):
        restartable = True

    return StepDetail(
        step_id="S00",
        agent_label="Worktree Setup",
        step_type="setup",
        status=status,
        duration_secs=dur,
        started_at=bi.started_at if bi else None,
        completed_at=None,
        error_message=bi.notes if bi and status == "failed" else None,
        run_count=0,
        is_synthetic=True,
        restartable=restartable,
    )


def _synthetic_merge_step(bi: BatchItem | None) -> StepDetail:
    """Build a synthetic StepDetail representing the squash-merge step.

    Args:
        bi: The most recent BatchItem for the work item, or None.

    Returns:
        A StepDetail with step_id ``"MERGE"`` and ``is_synthetic=True``.
    """
    status = _merge_status(bi)
    return StepDetail(
        step_id="MERGE",
        agent_label="Squash Merge",
        step_type="merge",
        status=status,
        duration_secs=None,
        started_at=None,
        completed_at=bi.merged_at if bi else None,
        error_message=bi.notes if bi and status == "failed" else None,
        run_count=0,
        is_synthetic=True,
    )


def _read_log_file(log_file: str | None) -> str | None:
    """Read log content directly from disk, stripping ANSI escape codes."""
    if log_file is None:
        return None
    path = Path(log_file)
    if not path.is_file():
        return None
    try:
        from orch.utils.log_capture import strip_ansi

        return strip_ansi(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def _get_log_modified(log_file: str | None) -> str | None:
    """Return human-readable last-modified time for a log file."""
    if log_file is None:
        return None
    path = Path(log_file)
    if not path.is_file():
        return None
    try:
        from datetime import datetime

        mtime = path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime, tz=UTC).astimezone()
        return dt.strftime("%H:%M:%S")
    except OSError:
        return None


def _reverse_log(content: str | None) -> str | None:
    """Return log content with lines in reverse order (newest first)."""
    if not content:
        return content
    lines = content.splitlines()
    lines.reverse()
    return "\n".join(lines)


def _setup_log_content(bi: BatchItem) -> str:
    """Build a human-readable log string for the worktree setup step.

    Args:
        bi: The BatchItem whose worktree_info and notes are formatted.

    Returns:
        Multi-line text summarising the setup outcome.
    """
    lines = ["=== Worktree Setup ==="]
    if bi.worktree_info and isinstance(bi.worktree_info, dict):
        lines.append(f"Path:       {bi.worktree_info.get('path', '-')}")
        lines.append(f"Branch:     {bi.worktree_info.get('branch', '-')}")
        lines.append(f"Created at: {bi.worktree_info.get('created_at', '-')}")
    else:
        lines.append("Worktree info not available.")
    if bi.notes:
        lines.append("")
        lines.append(f"Notes: {bi.notes}")
    return "\n".join(lines)


def _merge_log_content(bi: BatchItem) -> str:
    """Build a human-readable log string for the squash-merge step.

    Args:
        bi: The BatchItem whose merge_info and notes are formatted.

    Returns:
        Multi-line text summarising the merge outcome, including any pre-merge
        failure phase details from merge_info.
    """
    lines = ["=== Squash Merge ==="]
    if bi.merged_at:
        lines.append(f"Merged at: {bi.merged_at.isoformat()}")
    if bi.merge_info and isinstance(bi.merge_info, dict):
        # Pre-merge rebase failures and similar phase-tagged failures land here.
        phase = bi.merge_info.get("phase")
        if phase and bi.merge_info.get("success") is False:
            lines.append("")
            lines.append(f"--- pre-merge {phase} failure ---")
            summary = bi.merge_info.get("summary")
            if summary:
                lines.append(f"Summary: {summary}")
            for sha_key in ("worktree_base_sha", "current_main_sha"):
                if bi.merge_info.get(sha_key):
                    lines.append(f"{sha_key}: {bi.merge_info[sha_key]}")
            err = bi.merge_info.get("error_message")
            if err:
                lines.append("")
                lines.append(err)
        stdout = bi.merge_info.get("stdout", "")
        if stdout:
            lines.append("")
            lines.append("--- stdout ---")
            lines.append(stdout)
    if bi.notes:
        lines.append("")
        lines.append(f"Notes: {bi.notes}")
    if len(lines) == 1:
        lines.append("No merge output recorded.")
    return "\n".join(lines)


@dataclass
class ArtifactFile:
    """Deprecated - kept for backward compatibility with tests that import it.

    Use ``ArtifactNode`` and ``_list_artifact_tree`` instead.
    """

    name: str
    path: str
    size_bytes: int
    is_dir: bool = False


def _list_evidences(
    item: WorkItem, project: Project, db: Session, worktree_path: str | None = None
) -> list[EvidenceFile]:
    """Fetch evidences for item from DB first, then fall back to filesystem.

    DB is authoritative for completed/archived items; filesystem provides
    in-progress post-evidence snapshots written by browser verification
    agents that haven't flushed to the DB yet.
    """
    # DB-first
    rows = db.scalars(
        select(WorkItemEvidence).where(
            WorkItemEvidence.project_id == project.id,
            WorkItemEvidence.work_item_id == item.id,
        )
    ).all()
    seen: set[tuple[str, str]] = set()
    results: list[EvidenceFile] = []
    for row in rows:
        key = (row.phase.value, row.filename)
        if key in seen:
            continue
        seen.add(key)
        results.append(
            EvidenceFile(
                filename=row.filename,
                phase=row.phase.value,
                abs_path="",  # not from FS
                size_bytes=row.size_bytes,
                content=row.content,
                content_type=row.content_type,
            )
        )
    # FS fallback for in-progress post-evidence (worktree only)
    if worktree_path:
        rel_evidences = Path("ai-dev") / "active" / item.id / "evidences"
        base = Path(worktree_path) / rel_evidences
        for phase in ("pre", "post"):
            phase_dir = base / phase
            if not phase_dir.exists():
                continue
            try:
                for entry in sorted(phase_dir.iterdir()):
                    if entry.is_file():
                        key = (phase, entry.name)
                        if key not in seen:
                            seen.add(key)
                            results.append(
                                EvidenceFile(
                                    filename=entry.name,
                                    phase=phase,
                                    abs_path=str(entry),
                                    size_bytes=entry.stat().st_size,
                                )
                            )
            except OSError:
                pass
    return results


def _get_log_sections(project_id: str, item_id: str, db: Session) -> list[LogSection]:
    """Build the complete list of log sections for the logs tab.

    Returns one LogSection per workflow step (with per-run RunLog entries),
    preceded by a synthetic setup section and followed by a synthetic merge
    section.

    Args:
        project_id: Project owning the work item.
        item_id: Work item to load log sections for.
        db: Active database session.

    Returns:
        Ordered list of LogSection instances covering setup, real steps, and merge.
    """
    bi = _get_batch_item(project_id, item_id, db)

    setup_content = _setup_log_content(bi) if bi else "No batch item found."
    sections: list[LogSection] = [
        LogSection(
            step_id="S00",
            agent_label="Worktree Setup",
            status=_setup_status(bi),
            db_step_id=None,
            runs=[],
            static_content=setup_content,
        )
    ]

    workflow_steps = list(
        db.scalars(
            select(WorkflowStep)
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
            .order_by(WorkflowStep.step_number)
        ).all()
    )
    for step in workflow_steps:
        runs = list(
            db.scalars(
                select(StepRun).where(StepRun.step_id == step.id).order_by(StepRun.run_number)
            ).all()
        )
        run_logs = [
            RunLog(
                run_number=r.run_number,
                status=r.status.value,
                duration_secs=r.duration_secs,
                is_running=r.status.value == "running",
                log_content=_reverse_log(r.log_content or _read_log_file(r.log_file)),
                log_modified=_get_log_modified(r.log_file),
            )
            for r in runs
        ]
        sections.append(
            LogSection(
                step_id=step.step_id,
                agent_label=step.agent_label,
                status=step.status.value,
                db_step_id=step.id,
                runs=run_logs,
            )
        )

    merge_content = _merge_log_content(bi) if bi else "No batch item found."
    sections.append(
        LogSection(
            step_id="MERGE",
            agent_label="Squash Merge",
            status=_merge_status(bi),
            db_step_id=None,
            runs=[],
            static_content=merge_content,
        )
    )
    return sections


def _get_fix_cycles(project_id: str, item_id: str, db: Session) -> list[FixCycleDetail]:
    """Return all fix cycles for a work item, ordered by step then cycle number."""
    workflow_steps = list(
        db.scalars(
            select(WorkflowStep)
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
            .order_by(WorkflowStep.step_number)
        ).all()
    )
    if not workflow_steps:
        return []

    step_map = {s.id: s for s in workflow_steps}
    fix_cycles = list(
        db.scalars(
            select(FixCycle)
            .where(FixCycle.step_id.in_(list(step_map.keys())))
            .order_by(FixCycle.step_id, FixCycle.cycle_number)
        ).all()
    )

    result: list[FixCycleDetail] = []
    for fc in fix_cycles:
        step = step_map.get(fc.step_id)
        dur: float | None = None
        if fc.started_at and fc.completed_at:
            dur = (fc.completed_at - fc.started_at).total_seconds()

        log_file = (fc.fix_metadata or {}).get("log_file")
        raw_log = _read_log_file(log_file)
        log_content = _reverse_log(raw_log) if raw_log else None

        result.append(
            FixCycleDetail(
                id=fc.id,
                db_step_id=fc.step_id,
                step_id=step.step_id if step else "?",
                agent_label=step.agent_label if step else "?",
                cycle_number=fc.cycle_number,
                trigger_type=fc.trigger_type.value,
                status=fc.status.value,
                started_at=fc.started_at,
                completed_at=fc.completed_at,
                duration_secs=dur,
                log_content=log_content,
                log_modified=_get_log_modified(log_file),
                is_running=fc.status.value == "in_progress",
            )
        )
    return result


# ---------------------------------------------------------------------------
# Cascade history helpers (C.1, C.2, C.3)
# ---------------------------------------------------------------------------

_REPLAY_EVENT_TYPES = frozenset(
    {
        "cascaded_replay_after_fix",
        "review_replay_after_fix",
    }
)


def _get_cascade_history(db: Session, project_id: str, item_id: str) -> CascadeHistory:
    """Read cascade-related daemon events and step_runs; return a structured
    summary plus a tree of cascade events suitable for template rendering.

    One query per call - joins daemon_events filtered to the item and builds
    the causality tree in Python. No N+1 queries.
    """
    from sqlalchemy import func

    # 1. Fetch all cascade-related events for this item in chronological order.
    cascade_event_types = list(_REPLAY_EVENT_TYPES) + [
        "fix_cycle_started",
        "cascade_thrashing_detected",
    ]
    rows = list(
        db.scalars(
            select(DaemonEvent)
            .where(
                DaemonEvent.entity_id == item_id,
                DaemonEvent.event_type.in_(cascade_event_types),
            )
            .order_by(DaemonEvent.created_at)
        ).all()
    )

    # Separate by type
    replay_events: list[DaemonEvent] = []
    fix_cycle_events: list[DaemonEvent] = []
    thrashing_events: list[DaemonEvent] = []
    for ev in rows:
        if ev.event_type in _REPLAY_EVENT_TYPES:
            replay_events.append(ev)
        elif ev.event_type == "fix_cycle_started":
            fix_cycle_events.append(ev)
        elif ev.event_type == "cascade_thrashing_detected":
            thrashing_events.append(ev)

    cascade_event_count = len(replay_events)
    fix_cycle_count = len(fix_cycle_events)

    # 2. Build the thrashing alert (most recent event wins).
    thrashing: ThrashingAlert | None = None
    if thrashing_events:
        ev = thrashing_events[-1]
        meta = ev.event_metadata or {}
        thrashing = ThrashingAlert(
            trigger_step_id=meta.get("trigger_step_id", "?"),
            cascade_count=meta.get("cascade_count", 0),
            recommendation=meta.get("recommendation", "Manual review recommended."),
            created_at=ev.created_at,
        )

    if not replay_events:
        return CascadeHistory(
            cascade_event_count=0,
            fix_cycle_count=fix_cycle_count,
            replay_wall_clock_minutes=None,
            tree=[],
            thrashing=thrashing,
        )

    # 3. Compute replay wall-clock.
    # Simplification: (latest step_run completed_at across all step_runs) minus
    # (first cascade event timestamp). This approximates "how long did the replay
    # phase last". Documented simplification: we don't chase individual step
    # spans, we use the outer envelope.
    first_cascade_ts = replay_events[0].created_at

    workflow_step_db_ids = list(
        db.scalars(
            select(WorkflowStep.id).where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
        ).all()
    )

    replay_wall_clock_minutes: float | None = None
    if workflow_step_db_ids:
        latest_completed = db.scalar(
            select(func.max(StepRun.completed_at)).where(
                StepRun.step_id.in_(workflow_step_db_ids),
                StepRun.started_at >= first_cascade_ts,
            )
        )
        if latest_completed is not None:
            delta = (latest_completed - first_cascade_ts).total_seconds()
            replay_wall_clock_minutes = round(delta / 60, 1)

    # 4. Build causality tree.
    # Rule: cascade event E is a child of the most recent preceding cascade event
    # E' such that E.trigger_step_id is in E'.reset_step_ids.
    nodes: list[CascadeNode] = []
    for ev in replay_events:
        meta = ev.event_metadata or {}
        reset_ids: list[str] = list(meta.get("reset_step_ids", []))
        node = CascadeNode(
            timestamp=ev.created_at,
            trigger_step_id=meta.get("trigger_step_id", "?"),
            cycle_id=meta.get("cycle_id"),
            reset_step_ids=reset_ids,
            event_type=ev.event_type,
            changed_files=list(meta.get("changed_files", [])),
            review_reset_step_ids=list(meta.get("review_reset_step_ids", [])),
        )
        nodes.append(node)

    # Assign parent-child relationships
    top_level: list[CascadeNode] = []
    for i, node in enumerate(nodes):
        parent: CascadeNode | None = None
        # Search backwards for the most recent preceding event whose reset_step_ids
        # contains this node's trigger_step_id.
        for j in range(i - 1, -1, -1):
            candidate = nodes[j]
            if node.trigger_step_id in candidate.reset_step_ids:
                parent = candidate
                break
        if parent is not None:
            parent.children.append(node)
        else:
            top_level.append(node)

    return CascadeHistory(
        cascade_event_count=cascade_event_count,
        fix_cycle_count=fix_cycle_count,
        replay_wall_clock_minutes=replay_wall_clock_minutes,
        tree=top_level,
        thrashing=thrashing,
    )


# ---------------------------------------------------------------------------
# CR-00070 S01: inherited runtime label helper
# ---------------------------------------------------------------------------


def _get_inherited_runtime_label(
    db: Session,
    project_id: str,
    item: WorkItem,
) -> str | None:
    """Compute the display_name of the runtime an un-overridden step would inherit.

    Uses the same cascade as the daemon's resolve_runtime():
        item override → projects.toml (cli_tool, model) lookup → catalogue default

    Returns the resolved AgentRuntimeOption's display_name, or None when no
    option can be resolved (empty catalogue). A None value signals the template
    to fall back to a neutral "- inherit -" label (AC5).

    This function is called once per render (not per step) so the cascade result
    is identical for every per-step dropdown within the same work item.
    """
    from orch.agent_runtime.resolver import resolve_inherited_runtime
    from orch.config import load_config
    from orch.daemon.project_registry import load_projects_toml

    try:
        cfg = load_projects_toml(load_config().projects_toml)
        project_config = cfg.get(project_id)
    except Exception:
        # If projects.toml is unreadable, project_config stays None - the resolver
        # falls through to the catalogue default.
        project_config = None

    resolved = resolve_inherited_runtime(db, item=item, project=project_config)
    return resolved.display_name if resolved is not None else None


def _all_runtime_option_labels(db: Session) -> dict[int, dict[str, str]]:
    """Map every AgentRuntimeOption id → its labels, regardless of ``enabled``.

    The per-step dropdown only offers *enabled* options, but a completed step
    may reference an option that has since been disabled (e.g. a retired model
    like Opus 4.7). The read-only cli/model labels in the steps table resolve
    against this all-rows map so historical steps keep showing the runtime they
    actually ran on, instead of going blank once the option is disabled.
    """
    rows = db.scalars(select(AgentRuntimeOption)).all()
    return {
        r.id: {
            "cli_label": r.cli_label,
            "model_label": r.model_label,
            "display_name": r.display_name,
        }
        for r in rows
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/item/{item_id}", response_class=HTMLResponse)
def item_detail(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Render the full item detail page.

    Args:
        project_id: Project the item belongs to.
        item_id: Work item to display.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        Full-page HTML response for ``pages/project/item_detail.html``.
    """
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    steps = _get_steps(project_id, item_id, db)
    metrics = _get_metrics(project_id, item_id, steps, db)
    batch_ref = _get_batch_ref(project_id, item_id, db)
    batch_status = _get_batch_status(project_id, batch_ref, db)
    setup_error = _get_batch_item_error(project_id, item_id, db)

    # F-00081: fetch runtime options for dropdown population
    runtime_options = list(
        db.scalars(
            select(AgentRuntimeOption)
            .where(AgentRuntimeOption.enabled.is_(True))
            .order_by(AgentRuntimeOption.sort_order, AgentRuntimeOption.id)
        ).all()
    )
    runtime_options_list = [
        {
            "id": r.id,
            "cli_tool": r.cli_tool,
            "model": r.model,
            "cli_label": r.cli_label,
            "model_label": r.model_label,
            "display_name": r.display_name,
            "is_default": r.is_default,
        }
        for r in runtime_options
    ]
    item_runtime_option_id = item.agent_runtime_option_id

    # CR-00070 S01: compute the label shown in the per-step dropdown empty option
    inherited_runtime_label = _get_inherited_runtime_label(db, project_id, item)

    item_type_val = item.type
    item_status_val = item.status
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/item_detail.html",
        {
            "current_project": project,
            "running_count": 0,
            "item": item,
            "item_type": item_type_val.value if hasattr(item_type_val, "value") else item_type_val,
            "item_status": item_status_val.value
            if hasattr(item_status_val, "value")
            else item_status_val,
            "steps": steps,
            "metrics": metrics,
            "batch_ref": batch_ref,
            "batch_status": batch_status,
            "setup_error": setup_error,
            "runtime_options": runtime_options_list,
            "runtime_option_labels": _all_runtime_option_labels(db),
            "item_runtime_option_id": item_runtime_option_id,
            "inherited_runtime_label": inherited_runtime_label,
        },
    )


@router.get("/item/{item_id}/fragment/header", response_class=HTMLResponse)
def item_header_fragment(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: returns item header + metrics for live refresh."""
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    steps = _get_steps(project_id, item_id, db)
    metrics = _get_metrics(project_id, item_id, steps, db)
    batch_ref = _get_batch_ref(project_id, item_id, db)
    batch_status = _get_batch_status(project_id, batch_ref, db)
    setup_error = _get_batch_item_error(project_id, item_id, db)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_header.html",
        {
            "current_project": project,
            "item": item,
            "item_type": item.type.value,
            "item_status": item.status.value,
            "batch_ref": batch_ref,
            "batch_status": batch_status,
            "setup_error": setup_error,
            "metrics": metrics,
        },
    )


@router.get("/item/{item_id}/tab/overview", response_class=HTMLResponse)
def item_tab_overview(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: overview tab for an item, including steps and cascade history.

    Args:
        project_id: Project the item belongs to.
        item_id: Work item to display.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        HTML fragment for ``fragments/item_overview.html``.
    """
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    steps = _get_steps(project_id, item_id, db)
    cascade_history = _get_cascade_history(db, project_id, item_id)
    # C.1: run-count per step (step_id string → run count)
    step_run_counts: dict[str, int] = {s.step_id: s.run_count for s in steps if not s.is_synthetic}

    # F-00081: fetch runtime options for dropdown population
    runtime_options = list(
        db.scalars(
            select(AgentRuntimeOption)
            .where(AgentRuntimeOption.enabled.is_(True))
            .order_by(AgentRuntimeOption.sort_order, AgentRuntimeOption.id)
        ).all()
    )
    runtime_options_list = [
        {
            "id": r.id,
            "cli_tool": r.cli_tool,
            "model": r.model,
            "cli_label": r.cli_label,
            "model_label": r.model_label,
            "display_name": r.display_name,
            "is_default": r.is_default,
        }
        for r in runtime_options
    ]
    item_runtime_option_id = item.agent_runtime_option_id

    # CR-00070 S01: compute the label shown in the per-step dropdown empty option
    inherited_runtime_label = _get_inherited_runtime_label(db, project_id, item)

    # F-00090: compute top heuristic suggestion for the classification form
    top_suggestion = _top_suggestion(project_id, item_id, db)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_overview.html",
        {
            "current_project": project,
            "item": item,
            "steps": steps,
            "cascade_history": cascade_history,
            "step_run_counts": step_run_counts,
            "runtime_options": runtime_options_list,
            "runtime_option_labels": _all_runtime_option_labels(db),
            "item_runtime_option_id": item_runtime_option_id,
            "inherited_runtime_label": inherited_runtime_label,
            # F-00090: pass to the regression classification form
            "top_suggestion": top_suggestion,
        },
    )


@router.get("/item/{item_id}/step-runs/{step_id}", response_class=HTMLResponse)
def item_step_runs(
    project_id: str,
    item_id: str,
    step_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx endpoint: lazy-load run list for a single step (C.1 expansion)."""
    _get_project_or_404(project_id, db)
    _get_item_or_404(project_id, item_id, db)

    # Resolve the WorkflowStep DB id from the string step_id
    ws = db.scalar(
        select(WorkflowStep).where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.step_id == step_id,
        )
    )
    if ws is None:
        raise HTTPException(status_code=404, detail=f"Step {step_id!r} not found")

    runs = list(
        db.scalars(
            select(StepRun).where(StepRun.step_id == ws.id).order_by(StepRun.run_number)
        ).all()
    )

    run_rows = []
    for r in runs:
        dur: float | None = None
        if r.started_at and r.completed_at:
            dur = (r.completed_at - r.started_at).total_seconds()
        run_rows.append(
            {
                "run_number": r.run_number,
                "status": r.status.value,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "duration_secs": dur,
            }
        )

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/step_run_list.html",
        {
            "step_id": step_id,
            "runs": run_rows,
        },
    )


@router.get("/item/{item_id}/step/{step_id}/prompt-modal", response_class=HTMLResponse)
def get_prompt_modal(
    request: Request,
    project_id: str,
    item_id: str,
    step_id: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """htmx endpoint: render the prompt-text modal for a step (CR-00056 S06)."""
    # 404 if item does not exist
    work_item = db.scalar(
        select(WorkItem).where(
            WorkItem.project_id == project_id,
            WorkItem.id == item_id,
        )
    )
    if work_item is None:
        raise HTTPException(status_code=404, detail=f"Work item {item_id!r} not found")

    # 404 if step is not part of that item
    workflow_step = db.scalar(
        select(WorkflowStep).where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.step_id == step_id,
        )
    )
    if workflow_step is None:
        raise HTTPException(status_code=404, detail=f"Step {step_id!r} not found")

    # Fetch all runs ordered by run_number
    runs = list(
        db.scalars(
            select(StepRun).where(StepRun.step_id == workflow_step.id).order_by(StepRun.run_number)
        ).all()
    )

    # Build sections for the template
    sections: list[dict[str, str]] = []
    for r in runs:
        if r.prompt_text is not None:
            sections.append({"label": "Initial Prompt", "text": r.prompt_text})
        if r.fix_prompt_text is not None:
            sections.append(
                {"label": f"Fix Prompt (cycle {r.run_number - 1})", "text": r.fix_prompt_text}
            )

    if not sections:
        raise HTTPException(status_code=404, detail="No prompt text found for this step")

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/prompt_text_modal.html",
        {
            "request": request,
            "item": work_item,
            "step": workflow_step,
            "prompt_file_display": workflow_step.prompt_file or "",
            "sections": sections,
        },
    )


@router.get("/item/{item_id}/tab/design-doc", response_class=HTMLResponse)
def item_tab_design_doc(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: design-doc tab with rendered markdown.

    Args:
        project_id: Project the item belongs to.
        item_id: Work item whose design doc is displayed.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        HTML fragment for ``fragments/item_design_doc.html``.
    """
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)

    # Prefer archived Tier 1 content; fall back to reading from disk
    content: str | None = item.design_doc_content
    if content is None and item.design_doc_path and project.repo_root:
        disk_path = Path(project.repo_root) / item.design_doc_path
        try:
            content = disk_path.read_text(encoding="utf-8")
        except OSError:
            content = None

    design_doc_html = render_markdown(content)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_design_doc.html",
        {
            "item": item,
            "design_doc_html": design_doc_html,
            "has_content": bool(content),
        },
    )


@router.get("/item/{item_id}/tab/functional-doc", response_class=HTMLResponse)
def item_tab_functional_doc(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: functional-doc tab with rendered markdown.

    Args:
        project_id: Project the item belongs to.
        item_id: Work item whose functional doc is displayed.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        HTML fragment for ``fragments/item_functional_doc.html``.
    """
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)

    content: str | None = item.functional_doc_content
    if content is None and item.functional_doc_path and project.repo_root:
        disk_path = Path(project.repo_root) / item.functional_doc_path
        try:
            content = disk_path.read_text(encoding="utf-8")
        except OSError:
            content = None

    functional_doc_html = render_markdown(content)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_functional_doc.html",
        {
            "item": item,
            "functional_doc_html": functional_doc_html,
            "has_content": bool(content),
        },
    )


@router.get("/item/{item_id}/tab/reports", response_class=HTMLResponse)
def item_tab_reports(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: reports tab listing per-step rendered report content.

    Args:
        project_id: Project the item belongs to.
        item_id: Work item whose step reports are displayed.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        HTML fragment for ``fragments/item_reports.html``.
    """
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    steps = _get_steps(project_id, item_id, db, project=project)

    report_sections = [
        ReportSection(
            step_id=s.step_id,
            agent_label=s.agent_label,
            step_type=s.step_type,
            status=s.status,
            run_count=s.run_count,
            report_html=render_markdown(s.report_content),
        )
        for s in steps
        if s.report_content
    ]

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_reports.html",
        {
            "item": item,
            "report_sections": report_sections,
        },
    )


# ---------------------------------------------------------------------------
# Files view helpers
# ---------------------------------------------------------------------------


def _get_diff_text_and_summary(
    item: WorkItem,
    project: Project,
    step_run: StepRun | None,
    worktree_path: str | None,
) -> tuple[str | None, list[dict[str, Any]]]:
    """Resolve diff_text and summary for a files view scope.

    Returns (diff_text, summary). Summary is derived from stored diff_summary
    when available, otherwise parsed from diff_text via parse_diff_summary.
    """
    from orch.diff_service import parse_diff_summary, resolve_diff

    diff_text = resolve_diff(
        item=item, step_run=step_run, project=project, worktree_path=worktree_path
    )

    # Prefer stored summary over re-parsing
    stored_summary: list[dict[str, Any]] | None = None
    if step_run is not None:
        stored_summary = step_run.diff_summary
    elif item.diff_summary and item.archived_at:
        stored_summary = item.diff_summary

    if stored_summary is not None:
        return diff_text, stored_summary

    if diff_text:
        return diff_text, parse_diff_summary(diff_text)
    return None, []


def _step_options_from_item(item: WorkItem, db: Session) -> list[dict[str, Any]]:
    """Build step_options list from completed step_runs."""
    step_runs = db.scalars(
        select(StepRun)
        .where(
            StepRun.step_id.in_(
                select(WorkflowStep.id).where(
                    WorkflowStep.project_id == item.project_id,
                    WorkflowStep.work_item_id == item.id,
                )
            )
        )
        .where(StepRun.status.in_([RunStatus.completed, RunStatus.failed]))
    ).all()
    # Group by step
    seen: set[int] = set()
    options: list[dict[str, Any]] = []
    for sr in sorted(step_runs, key=lambda r: r.run_number):
        if sr.step_id in seen:
            continue
        seen.add(sr.step_id)
        ws = db.scalar(select(WorkflowStep).where(WorkflowStep.id == sr.step_id))
        step_label = ws.step_label if ws else sr.step_id
        options.append(
            {
                "step_id": str(sr.step_id),
                "step_name": step_label,
                "has_diff": bool(sr.diff_text),
            }
        )
    return options


def _render_diff_hunks(diff_text: str, summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Render hunks_html for each file in summary (up to PDF cap of 100)."""
    import unidiff

    results: list[dict[str, Any]] = []
    patch_set = unidiff.PatchSet(diff_text)
    path_to_entry = {entry["path"]: entry for entry in summary}

    formatter = HtmlFormatter(full=True, cssclass="highlight", nowrap=False)
    cap = 100
    for idx, patched_file in enumerate(patch_set):
        path = patched_file.target_file.lstrip("b/") or patched_file.source_file.lstrip("a/")
        entry = path_to_entry.get(path, {})
        if idx >= cap or entry.get("is_binary"):
            results.append({**entry, "hunks_html": None})
            continue

        # Count total lines to detect large files
        total_lines = sum(hunk.added + hunk.removed for hunk in patched_file)
        if total_lines >= 5000:
            results.append({**entry, "hunks_html": None})
            continue

        hunks_html_parts: list[str] = []
        for hunk in patched_file:
            hunks_html_parts.append(highlight(str(hunk), DiffLexer(), formatter))
        results.append({**entry, "hunks_html": Markup().join(hunks_html_parts)})

    # Add truncated files (past cap, not already in results)
    capped_paths = {r["path"] for r in results}
    for entry in summary:
        if entry["path"] in capped_paths:
            continue
        if len(results) >= cap:
            results.append({**entry, "hunks_html": None})

    return results


# ---------------------------------------------------------------------------
# Files view routes
# ---------------------------------------------------------------------------


@router.get("/item/{item_id}/tab/files", response_class=HTMLResponse)
def item_tab_files(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Render the Files tab shell as an htmx fragment."""
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    bi = _get_batch_item(project_id, item_id, db)
    worktree_path = bi.worktree_info.get("path") if bi and bi.worktree_info else None
    worktree_alive = worktree_path is not None and Path(worktree_path).exists()
    is_archived = item.archived_at is not None

    diff_text, summary = _get_diff_text_and_summary(
        item=item, project=project, step_run=None, worktree_path=worktree_path
    )

    aggregate_added = sum(f["added"] for f in summary)
    aggregate_removed = sum(f["removed"] for f in summary)
    aggregate_file_count = len(summary)
    default_expand_all = len(summary) <= 10

    step_options = _step_options_from_item(item, db)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_files.html",
        {
            "item": item,
            "project_id": project_id,
            "summary": summary,
            "step_options": step_options,
            "worktree_alive": worktree_alive,
            "is_archived": is_archived,
            "aggregate_added": aggregate_added,
            "aggregate_removed": aggregate_removed,
            "aggregate_file_count": aggregate_file_count,
            "default_expand_all": default_expand_all,
        },
    )


@router.get("/item/{item_id}/files/diff")
def item_files_diff(
    project_id: str,
    item_id: str,
    step: str = Query("all"),
    db: Session = Depends(get_db),
) -> Response:
    """Return raw unified diff text for the requested scope."""
    _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)

    step_run: StepRun | None = None
    if step != "all":
        try:
            step_db_id = int(step)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid step id: {step!r}") from err
        step_run = db.scalar(
            select(StepRun).where(
                StepRun.id == step_db_id,
                StepRun.step_id.in_(
                    select(WorkflowStep.id).where(
                        WorkflowStep.project_id == project_id,
                        WorkflowStep.work_item_id == item_id,
                    )
                ),
            )
        )
        if step_run is None:
            raise HTTPException(status_code=404, detail="Step run not found")

    project = _get_project_or_404(project_id, db)
    bi = _get_batch_item(project_id, item_id, db)
    worktree_path = bi.worktree_info.get("path") if bi and bi.worktree_info else None

    diff_text, _ = _get_diff_text_and_summary(
        item=item, project=project, step_run=step_run, worktree_path=worktree_path
    )

    if diff_text is None:
        return Response(content="", media_type="text/plain", headers={"X-Diff-Empty": "1"})
    return Response(content=diff_text, media_type="text/plain")


@router.get("/item/{item_id}/files/untracked")
def item_files_untracked(
    project_id: str,
    item_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """Return JSON list of untracked worktree files."""
    _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    bi = _get_batch_item(project_id, item_id, db)
    worktree_path = (bi.worktree_info or {}).get("path") if bi else None

    if item.archived_at is not None or not worktree_path or not Path(worktree_path).exists():
        return Response(
            content='{"files": []}',
            media_type="application/json",
            headers={"X-Untracked-Disabled": "archived" if item.archived_at else "no-worktree"},
        )

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],  # noqa: S603,S607
            capture_output=True,
            text=True,
            cwd=worktree_path,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return Response(content='{"files": []}', media_type="application/json")
    except Exception:
        return Response(content='{"files": []}', media_type="application/json")

    exclude_prefixes = (
        "ai-dev/active/",
        "ai-dev/archive/",
        "ai-dev/design/",
    )
    files: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if not line.startswith("?? "):
            continue
        rel_path = line[3:].strip('"').lstrip("/")
        if any(rel_path.startswith(p) for p in exclude_prefixes):
            continue
        full_path = Path(worktree_path) / rel_path
        if not full_path.is_file():
            continue
        files.append(
            {
                "path": rel_path,
                "size_bytes": full_path.stat().st_size,
                "file_type": _detect_file_type(rel_path),
            }
        )

    return Response(content=json.dumps({"files": files}), media_type="application/json")


@router.get("/item/{item_id}/files/export.pdf")
def item_files_export_pdf(
    project_id: str,
    item_id: str,
    request: Request,
    step: str = Query("all"),
    db: Session = Depends(get_db),
) -> Response:
    """Render WeasyPrint PDF of the diff for the requested scope."""
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)

    step_run: StepRun | None = None
    if step != "all":
        try:
            step_db_id = int(step)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid step id: {step!r}") from err
        step_run = db.scalar(
            select(StepRun).where(
                StepRun.id == step_db_id,
                StepRun.step_id.in_(
                    select(WorkflowStep.id).where(
                        WorkflowStep.project_id == project_id,
                        WorkflowStep.work_item_id == item_id,
                    )
                ),
            )
        )
        if step_run is None:
            raise HTTPException(status_code=404, detail="Step run not found")

    bi = _get_batch_item(project_id, item_id, db)
    worktree_path = (bi.worktree_info or {}).get("path") if bi else None

    diff_text, summary = _get_diff_text_and_summary(
        item=item, project=project, step_run=step_run, worktree_path=worktree_path
    )

    aggregate_added = sum(f["added"] for f in summary)
    aggregate_removed = sum(f["removed"] for f in summary)
    aggregate_file_count = len(summary)

    step_label = "All steps" if step == "all" else f"Step {step}"
    if step != "all" and step_run:
        ws = db.scalar(select(WorkflowStep).where(WorkflowStep.id == step_run.step_id))
        if ws and ws.step_label:
            step_label = ws.step_label

    hunks_files = _render_diff_hunks(diff_text or "", summary)
    summary_files = hunks_files[:100]
    truncated_files = hunks_files[100:]

    templates: Jinja2Templates = request.app.state.templates
    try:
        pdf_template = templates.get_template("exports/diff_pdf.html")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Template error: {exc}") from exc
    try:
        html_content = pdf_template.render(
            item=item,
            project_id=project_id,
            step_label=step_label,
            aggregate_added=aggregate_added,
            aggregate_removed=aggregate_removed,
            aggregate_file_count=aggregate_file_count,
            summary_files=summary_files,
            truncated_files=truncated_files,
            generated_at=_now_iso(),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Template render error: {exc}") from exc

    try:
        from weasyprint import HTML as WeasyHTML  # noqa: N811

        pdf_bytes = WeasyHTML(string=html_content).write_pdf()
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="WeasyPrint not installed") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}") from exc

    filename = f"{item_id}_files_{step}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/item/{item_id}/artifact-raw")
def item_artifact_raw(
    project_id: str,
    item_id: str,
    path: str,
    db: Session = Depends(get_db),
) -> Response:
    """Serve a raw artifact file by relative path.

    Path traversal protection: the resolved path must be within the artifact root.
    """
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    bi = _get_batch_item(project_id, item_id, db)
    worktree_path = bi.worktree_info.get("path") if bi and bi.worktree_info else None
    artifact_root = _resolve_artifact_root(item, project, worktree_path)
    if artifact_root is None:
        raise HTTPException(status_code=404, detail="Artifact root not found")

    # Resolve the requested file and protect against traversal
    try:
        requested = (artifact_root / path).resolve()
        requested.relative_to(artifact_root.resolve())
    except ValueError as err:
        raise HTTPException(status_code=403, detail="Access denied") from err

    if not requested.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    content_type, _ = mimetypes.guess_type(path)
    content_type = content_type or "application/octet-stream"
    try:
        data = requested.read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not read file") from exc
    return Response(content=data, media_type=content_type)


@router.get("/item/{item_id}/tab/logs", response_class=HTMLResponse)
def item_tab_logs(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: logs tab showing per-step run logs.

    Args:
        project_id: Project the item belongs to.
        item_id: Work item whose logs are displayed.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        HTML fragment for ``fragments/item_logs.html``.
    """
    _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    log_sections = _get_log_sections(project_id, item_id, db)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_logs.html",
        {
            "item": item,
            "log_sections": log_sections,
            "project_id": project_id,
        },
    )


@router.get("/item/{item_id}/tab/fix-cycles", response_class=HTMLResponse)
def item_tab_fix_cycles(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: fix-cycles tab listing all fix cycles for an item.

    Args:
        project_id: Project the item belongs to.
        item_id: Work item whose fix cycles are displayed.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        HTML fragment for ``fragments/item_fix_cycles.html``.
    """
    _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    fix_cycles = _get_fix_cycles(project_id, item_id, db)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_fix_cycles.html",
        {
            "item": item,
            "project_id": project_id,
            "fix_cycles": fix_cycles,
        },
    )


@router.get("/item/{item_id}/execution-report", response_class=HTMLResponse)
def item_execution_report(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Render the standalone execution report page for an item.

    Args:
        project_id: Project the item belongs to.
        item_id: Work item whose execution report is displayed.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        Full-page HTML response for ``pages/project/item_execution_report.html``.
    """
    _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    execution_report = assemble_execution_report(db, project_id, item_id)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/item_execution_report.html",
        {
            "current_project": _get_project_or_404(project_id, db),
            "item": item,
            "execution_report": execution_report,
        },
    )


@router.get("/item/{item_id}/tab/execution-report", response_class=HTMLResponse)
def item_tab_execution_report(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: execution-report tab for the item detail page.

    Args:
        project_id: Project the item belongs to.
        item_id: Work item whose execution report is displayed.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        HTML fragment for ``fragments/item_execution_report.html``.
    """
    _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    execution_report = assemble_execution_report(db, project_id, item_id)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_execution_report.html",
        {
            "item": item,
            "execution_report": execution_report,
        },
    )


@router.get("/item/{item_id}/tab/evidences", response_class=HTMLResponse)
def item_tab_evidences(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: evidences tab showing pre/post screenshots.

    Args:
        project_id: Project the item belongs to.
        item_id: Work item whose evidences are displayed.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        HTML fragment for ``fragments/item_evidences.html``.
    """
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)
    bi = _get_batch_item(project_id, item_id, db)
    worktree_path = (bi.worktree_info or {}).get("path") if bi else None
    evidences = _list_evidences(item, project, db, worktree_path)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_evidences.html",
        {
            "item": item,
            "project_id": project_id,
            "evidences": evidences,
            "pre_evidences": [e for e in evidences if e.phase == "pre"],
            "post_evidences": [e for e in evidences if e.phase == "post"],
        },
    )


@router.get("/item/{item_id}/evidence/{phase}/{filename}")
def item_evidence_file(
    project_id: str,
    item_id: str,
    phase: str,
    filename: str,
    db: Session = Depends(get_db),
) -> Response:
    """Serve a single evidence image file (DB-first, FS fallback for in-progress)."""
    if phase not in ("pre", "post"):
        raise HTTPException(status_code=404, detail="Invalid evidence phase")
    project = _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)

    # DB-first
    row = db.scalars(
        select(WorkItemEvidence).where(
            WorkItemEvidence.project_id == project_id,
            WorkItemEvidence.work_item_id == item_id,
            WorkItemEvidence.phase == EvidencePhase(phase),
            WorkItemEvidence.filename == filename,
        )
    ).first()
    if row is not None:
        return Response(
            content=row.content,
            media_type=row.content_type,
        )

    # FS fallback for in-progress post-evidence
    evidence_path = (
        Path(project.repo_root) / "ai-dev" / "active" / item.id / "evidences" / phase / filename
    )
    try:
        evidence_path.resolve().relative_to(
            (Path(project.repo_root) / "ai-dev" / "active" / item.id / "evidences").resolve()
        )
    except ValueError as err:
        raise HTTPException(status_code=403, detail="Access denied") from err
    if not evidence_path.is_file():
        raise HTTPException(status_code=404, detail="Evidence file not found")
    content_type, _ = mimetypes.guess_type(filename)
    content_type = content_type or "application/octet-stream"
    try:
        data = evidence_path.read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not read file") from exc
    return Response(content=data, media_type=content_type)


@router.get("/item/{item_id}/log-content/{step_db_id}/{run_number}", response_class=HTMLResponse)
def item_log_content(
    project_id: str,
    item_id: str,
    step_db_id: int,
    run_number: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: refreshable log content panel for a single step run.

    Args:
        project_id: Project the item belongs to.
        item_id: Work item the step belongs to.
        step_db_id: Database id of the WorkflowStep.
        run_number: Run number within the step to display.
        request: Incoming FastAPI request (used to resolve templates).
        db: Active database session.

    Returns:
        HTML fragment for ``fragments/item_log_content.html``.
    """
    _get_item_or_404(project_id, item_id, db)
    run = db.scalar(
        select(StepRun).where(
            StepRun.step_id == step_db_id,
            StepRun.run_number == run_number,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    log_content = _reverse_log(run.log_content or _read_log_file(run.log_file))
    log_modified = _get_log_modified(run.log_file)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/item_log_content.html",
        {
            "log_content": log_content,
            "log_modified": log_modified,
            "is_running": run.status.value == "running",
            "project_id": project_id,
            "item_id": item_id,
            "step_db_id": step_db_id,
            "run_number": run_number,
        },
    )


@router.get("/item/{item_id}/step/{step_id}/session-log", response_class=HTMLResponse)
def item_session_log(
    project_id: str,
    item_id: str,
    step_id: str,
    request: Request,
    run_number: int | None = None,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: rendered session log for a specific step run (CR-00065).

    Query params:
        run_number: int | None - if omitted, uses the highest run_number for the step.

    Error handling:
        404 if project, item, or step not found.
        200 with error segment if read_session_content fails (never 500).
    """
    from orch.daemon.session_reader import group_into_turns_newest_first, read_session_content

    # Validate project + item exist
    _get_project_or_404(project_id, db)
    _get_item_or_404(project_id, item_id, db)

    # Resolve the WorkflowStep DB id from the string step_id
    ws = db.scalar(
        select(WorkflowStep).where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.step_id == step_id,
        )
    )
    if ws is None:
        raise HTTPException(status_code=404, detail=f"Step {step_id!r} not found")

    # Query StepRun rows for this step
    run: StepRun | None = None
    if run_number is not None:
        run = db.scalar(
            select(StepRun).where(
                StepRun.step_id == ws.id,
                StepRun.run_number == run_number,
            )
        )
    else:
        # Default to the latest run (highest run_number)
        run = db.scalars(
            select(StepRun)
            .where(StepRun.step_id == ws.id)
            .order_by(StepRun.run_number.desc())
            .limit(1)
        ).first()

    turns: list[list[dict[str, Any]]] = []
    cli_tool: str | None = None
    is_live: bool = False
    error_message: str | None = None

    if run is not None:
        cli_tool = run.cli_tool
        is_live = run.status in (RunStatus.running, RunStatus.stalled)
        error_message = run.error_message
        try:
            raw_segments = read_session_content(run)
            turns = group_into_turns_newest_first(raw_segments)
            # Never 500 - return a single error segment so the popup still renders
        except Exception:
            error_segment = {
                "type": "error",
                "text": "Failed to read session log.",
                "collapsible": False,
            }
            turns = [[error_segment]]

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/session_log_popup_content.html",
        {
            "turns": turns,
            "is_live": is_live,
            "step_id": step_id,
            "run_number": run.run_number if run is not None else 1,
            "cli_tool": cli_tool,
            "item_id": item_id,
            "project_id": project_id,
            "error_message": error_message,
        },
    )


# ---------------------------------------------------------------------------
# F-00090: Regression classification endpoints (AC5)
# ---------------------------------------------------------------------------


def _top_suggestion(
    project_id: str,
    item_id: str,
    db: Session,
) -> Candidate | None:
    """Return the top heuristic suggestion (or None) for an incident.

    Calls suggest_introducer and returns the first candidate, if any.
    Returns None when suggest_introducer returns [] (no git repo, unmerged,
    or no file overlap found).
    """
    from orch.regression_link_service import suggest_introducer  # noqa: PLC0415

    try:
        candidates = suggest_introducer(
            db,
            project_id=project_id,
            item_id=item_id,
        )
        return candidates[0] if candidates else None
    except Exception:
        # Git calls can fail when the repo path is wrong or git is unavailable.
        # Never surface these as 500 - just return None so the accept button is hidden.
        return None


@router.get("/item/{item_id}/regression-suggestions", response_class=HTMLResponse)
def item_regression_suggestions(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx endpoint: return the ranked heuristic suggestion list fragment.

    Used by the 'Refresh suggestions' button in the classification form.
    Swapping: the caller targets #regression-suggestion-list and swaps its innerHTML.
    """
    _get_project_or_404(project_id, db)
    _get_item_or_404(project_id, item_id, db)

    from orch.regression_link_service import suggest_introducer  # noqa: PLC0415

    try:
        candidates = suggest_introducer(
            db,
            project_id=project_id,
            item_id=item_id,
        )
    except Exception:
        candidates = []

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/regression_suggestion_list.html",
        {
            "project_id": project_id,
            "item_id": item_id,
            "candidates": candidates,
        },
    )


_RE_SHA_PATTERN = __import__("re").compile(r"^[0-9a-fA-F]{7,40}$")


@router.post("/item/{item_id}/regression-classify")
async def item_regression_classify(
    project_id: str,
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx endpoint: classify an Incident against the merge that introduced the regression.

    Reads form fields from the request.
    Calls regression_link_service.classify(...) and either:
    - Returns the re-rendered form fragment with an inline error (422 on ValueError)
    - Returns the updated item row fragment (200 on success)

    The 'accept_top' field causes classified_by to be set to 'heuristic:auto' instead
    of the default 'operator:{user}' path.
    """
    from orch.regression_link_service import classify as _svc_classify

    _get_project_or_404(project_id, db)
    item = _get_item_or_404(project_id, item_id, db)

    # Parse form fields - request.form() is async but FastAPI awaits it
    form_data = await request.form()
    introduced_by_work_item_id = (
        str(form_data.get("introduced_by_work_item_id", "")).strip() or None
    )
    commit_sha = str(form_data.get("commit_sha", "")).strip() or None
    classification_str = str(form_data.get("classification", "")).strip()
    accept_top = str(form_data.get("accept_top", "")).strip()
    clear_flag = str(form_data.get("clear", "")).strip()

    # Validate classification is one of the enum values
    valid_classifications = {e.value for e in RegressionClassification}
    if classification_str not in valid_classifications:
        err = (
            '<div class="p-3 bg-destructive/10 border border-destructive/30 "'
            'rounded text-sm text-destructive">'
            "Please select a classification "
            "(regression, pre-existing, or unknown)."
            "</div>"
        )
        return HTMLResponse(err, status_code=422, media_type="text/html")

    classification = RegressionClassification(classification_str)

    # Validate commit SHA format
    if commit_sha and not _RE_SHA_PATTERN.match(commit_sha):
        templates: Jinja2Templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "fragments/regression_classification_form.html",
            {
                "project_id": project_id,
                "item_id": item_id,
                "item": item,
                "top_suggestion": _top_suggestion(project_id, item_id, db),
                "error_message": (
                    "Commit SHA must be 7-40 hexadecimal characters (e.g. a1b2c3d or "
                    "a1b2c3d4e5f6...)."
                ),
            },
            status_code=422,
        )

    # Determine classified_by
    current_user = request.headers.get("X-User-Name", "unknown")
    classified_by = "heuristic:auto" if accept_top else f"operator:{current_user}"

    # Handle clear
    if clear_flag:
        introduced_by_work_item_id = None
        commit_sha = None
        classification = RegressionClassification.unknown
        classified_by = f"operator:{current_user}"

    # Call service - on ValueError return form with error
    try:
        updated_item = _svc_classify(
            db,
            project_id=project_id,
            item_id=item_id,
            introduced_by_work_item_id=introduced_by_work_item_id,
            introduced_by_commit_sha=commit_sha,
            classification=classification,
            classified_by=classified_by,
        )
    except ValueError as exc:
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "fragments/regression_classification_form.html",
            {
                "project_id": project_id,
                "item_id": item_id,
                "item": item,
                "top_suggestion": _top_suggestion(project_id, item_id, db),
                "error_message": str(exc),
            },
            status_code=422,
        )
    except LookupError as exc:
        return HTMLResponse(
            '<div class="p-3 bg-destructive/10 border border-destructive/30 '
            'rounded text-sm text-destructive">' + str(exc) + "</div>",
            status_code=404,
            media_type="text/html",
        )

    # Success: return updated classification form (reflects new values)
    db.commit()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/regression_classification_form.html",
        {
            "project_id": project_id,
            "item_id": item_id,
            "item": updated_item,
            "top_suggestion": _top_suggestion(project_id, item_id, db),
            "error_message": None,
        },
    )
