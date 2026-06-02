"""Batch list and batch detail routes."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import (  # noqa: N811  UTC used at runtime in _get_held_reasons; datetime class used at runtime (datetime.now) and in type annotations via PEP 563
    UTC,
    datetime,
)
from typing import TYPE_CHECKING, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from dashboard.dependencies import get_db
from dashboard.routers.project_dashboard import (
    regression_count_for_merge as _regression_count_for_merge,
)
from dashboard.utils.batch_progress import compute_batch_step_progress
from orch.db.models import (
    AgentRuntimeOption,
    Batch,
    BatchItem,
    BatchStatus,
    DaemonEvent,
    FixCycle,
    Project,
    WorkflowStep,
    WorkItem,
)

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session


router = APIRouter(prefix="/project/{project_id}")

_ALL_STATUSES = [s.value for s in BatchStatus]
_HIDDEN_STATUSES = {"published", "publish_failed"}
_VISIBLE_STATUSES = [s for s in _ALL_STATUSES if s not in _HIDDEN_STATUSES]
_ACTIVE_STATUSES = [s for s in _VISIBLE_STATUSES if s not in ("archived", "cancelled")]


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class StepNode:
    """Minimal step info for the step_pipeline macro (strings, not enums)."""

    step_id: str
    agent_label: str
    status: str
    duration: str = ""
    duration_secs: float | None = None
    fix_cycle_count: int = 0


@dataclass
class BatchItemRow:
    """A work item inside a batch, with its step pipeline."""

    item_id: str
    title: str
    execution_group: int
    status: str
    steps: list[StepNode] = field(default_factory=list)
    duration_secs: float | None = None
    started_at: datetime | None = None
    started_at_ts: float | None = None
    ended_at_ts: float | None = None
    # CR-00058: scope-gate status — held or policy_allowed (replaces held_reason)
    scope_status: ScopeStatus | None = None
    # F-00081: item-level runtime override (None = default)
    runtime_option_id: int | None = None
    runtime_option_cli_label: str | None = None
    runtime_option_model_label: str | None = None
    # F-00081: step-level override dot — True if any step has its own override
    has_step_override: bool = False
    regression_count: int = 0
    """F-00090 AC7: count of regressions introduced by this item (prefetched; avoids N+1)."""


@dataclass
class ScopeStatus:
    """CR-00058: scope-gate status for a batch item — either held or policy_allowed."""

    status: Literal["held", "policy_allowed"]
    message: str
    matched_globs: list[str]
    matched_allow_patterns: list[str]  # only populated for policy_allowed
    blocking_item_ids: list[str]

    @property
    def pill_text(self) -> str:
        """Short text for the pill label."""
        if self.status == "held":
            globs = self.matched_globs
            if len(globs) >= 2:
                glob_summary = f"{globs[0]}, {globs[1]}+{len(globs) - 2}"
            elif len(globs) == 1:
                glob_summary = globs[0]
            else:
                glob_summary = "overlap"
            blockers = ", ".join(self.blocking_item_ids)
            return f"Held: overlaps with {blockers} on `{glob_summary}`"
        patterns = self.matched_allow_patterns
        if len(patterns) > 3:
            shown = ", ".join(patterns[:3]) + f"+{len(patterns) - 3} more"
        else:
            shown = ", ".join(patterns)
        return f"policy allowed ({shown})"

    @property
    def pill_tooltip(self) -> str:
        """Full tooltip text listing all patterns and blocking items."""
        parts = []
        if self.matched_allow_patterns:
            parts.append(f"Matched allow patterns: {', '.join(self.matched_allow_patterns)}")
        if self.matched_globs:
            parts.append(f"Conflicting globs: {', '.join(self.matched_globs)}")
        if self.blocking_item_ids:
            parts.append(f"Blocking items: {', '.join(self.blocking_item_ids)}")
        return " | ".join(parts)


@dataclass
class BatchRow:
    """A batch row for the list view."""

    id: str
    status: str
    total_items: int
    completed_items: int
    progress_pct: int
    created_at: datetime
    duration_secs: float | None
    # C.4: how many work items in this batch had cascade replay events
    cascade_item_count: int = 0


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _get_scope_statuses(
    project_id: str,
    item_ids: list[str],
    db: Session,
    window_secs: int = 300,
) -> dict[str, ScopeStatus]:
    """CR-00058: for each given work_item_id in project, return the most recent
    scope-gate DaemonEvent (within window_secs) as a ScopeStatus record.

    Queries both event types in a single combined query:
    - item_held_for_scope → status='held'
    - item_overlap_allowed_by_policy → status='policy_allowed'

    Held takes precedence over policy_allowed when both exist within the window
    for the same item.

    Returns a dict {work_item_id: ScopeStatus} for items with a recent event.
    Items with no event are absent from the dict (scope_status=None in rows).
    """
    from datetime import timedelta

    from orch.db.models import DaemonEvent

    if not item_ids:
        return {}

    cutoff = datetime.now(UTC) - timedelta(seconds=window_secs)
    rows = (
        db.execute(
            select(DaemonEvent)
            .where(
                DaemonEvent.project_id == project_id,
                DaemonEvent.event_type.in_(
                    ("item_held_for_scope", "item_overlap_allowed_by_policy")
                ),
                DaemonEvent.entity_id.in_(item_ids),
                DaemonEvent.entity_type == "work_item",
                DaemonEvent.created_at >= cutoff,
            )
            .order_by(DaemonEvent.entity_id, DaemonEvent.created_at.desc())
        )
        .scalars()
        .all()
    )

    # Build per-item status: held takes precedence over policy_allowed.
    # Scan in forward order (oldest-first) so that oldest-event globs appear first
    # in all_globs / matched_globs (preserving chronological order for the pill text).
    # After scanning, build the final Status objects for any entity that has a held
    # event; policy_allowed is applied only when no held event exists for that entity.
    # For held events, accumulate all globs from all events (forward scan with
    # ordered deduplication so glob order matches event order).
    item_statuses: dict[str, ScopeStatus] = {}
    item_blocking_globs: dict[str, dict[str, list[str]]] = {}  # entity_id → blocking_id → globs
    item_policy_allowed: dict[str, ScopeStatus] = {}  # entity_id → policy_allowed Status
    for ev in rows:
        entity_id = ev.entity_id
        if entity_id is None:
            continue
        meta = ev.event_metadata or {}
        if ev.event_type == "item_held_for_scope":
            blocking = meta.get("blocking_item_id", "")
            globs: list[str] = list(meta.get("conflicting_globs", []))
            if not globs:
                continue
            # Accumulate globs per blocking item using an ordered list with
            # deduplication so glob order reflects event order for pill text
            if entity_id not in item_blocking_globs:
                item_blocking_globs[entity_id] = {}
            if blocking not in item_blocking_globs[entity_id]:
                item_blocking_globs[entity_id][blocking] = []
            existing = item_blocking_globs[entity_id][blocking]
            for g in globs:
                if g not in existing:
                    existing.append(g)
        elif ev.event_type == "item_overlap_allowed_by_policy":
            # Record policy_allowed but don't finalise yet — held may override
            if entity_id in item_blocking_globs:
                continue
            in_flight_ids: list[str] = list(meta.get("in_flight_item_ids", []))
            allow_patterns: list[str] = list(meta.get("matched_allow_patterns", []))
            dropped: list[str] = list(meta.get("dropped_block_globs", []))
            # Build message
            blockers = ", ".join(in_flight_ids) if in_flight_ids else "overlap"
            patterns_str = ", ".join(allow_patterns[:3])
            if len(allow_patterns) > 3:
                patterns_str += f"+{len(allow_patterns) - 3} more"
            message = f"Released by allow pattern {patterns_str} — overlapped with {blockers}"
            status = ScopeStatus(
                status="policy_allowed",
                message=message,
                matched_globs=dropped,
                matched_allow_patterns=allow_patterns,
                blocking_item_ids=in_flight_ids,
            )
            item_policy_allowed[entity_id] = status
    # Finalise: held takes precedence over policy_allowed
    for entity_id, blocking_map in item_blocking_globs.items():
        all_globs = [g for bset in blocking_map.values() for g in bset]
        status = ScopeStatus(
            status="held",
            message="",
            matched_globs=all_globs,
            matched_allow_patterns=[],
            blocking_item_ids=list(blocking_map.keys()),
        )
        item_statuses[entity_id] = status
    for entity_id, status in item_policy_allowed.items():
        if entity_id not in item_statuses:
            item_statuses[entity_id] = status
    return item_statuses


def _get_held_reasons(
    project_id: str,
    item_ids: list[str],
    db: Session,
    window_secs: int = 300,
) -> dict[str, str]:
    """F-00076 (backwards compat): wraps _get_scope_statuses, returns the
    old {work_item_id: reason_str} dict for existing call sites."""
    statuses = _get_scope_statuses(project_id, item_ids, db, window_secs)
    return {item_id: s.pill_text for item_id, s in statuses.items() if s.status == "held"}


def group_overlap_events(
    events: list[DaemonEvent],
) -> list[tuple[str, list[str]]]:
    """Return ordered (blocking_item_id, conflicting_globs) tuples.

    Most-recent-wins on duplicate blocking_item_ids (events arrive newest first).
    Events whose `event_metadata` lacks the required keys are silently skipped.
    Insertion order across distinct blocking_item_ids is preserved.

    Handles both `blocking_item_id` (newer events from CR-00077 daemon) and
    `blocker_item_id` (legacy events) keys in event_metadata for backward
    compatibility with older DaemonEvent rows in production seed data.

    Accumulates ALL globs from ALL events for each blocking_item_id so that
    the modal shows the complete list regardless of how many events were
    generated during daemon scope-checking cycles.
    """
    seen: dict[str, set[str]] = {}
    # Iterate in forward order so the first occurrence we see (oldest event)
    # sets the key ordering, but we union all globs across all occurrences
    # so nothing is lost.
    for ev in events:
        meta = ev.event_metadata or {}
        # Support both legacy (blocker_item_id) and new (blocking_item_id) key names
        blocking_id: str | None = meta.get("blocking_item_id") or meta.get("blocker_item_id")
        globs: list[str] | None = meta.get("conflicting_globs")
        if not blocking_id or not globs:
            continue
        if blocking_id not in seen:
            seen[blocking_id] = set()
        seen[blocking_id].update(globs)
    # Build result in first-appearance order (oldest-first from original list)
    result: list[tuple[str, list[str]]] = []
    for ev in events:
        meta = ev.event_metadata or {}
        bid: str | None = meta.get("blocking_item_id") or meta.get("blocker_item_id")
        if bid and bid in seen and (bid, sorted(seen[bid])) not in result:
            result.append((bid, sorted(seen[bid])))
    return result


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


def _get_batch_or_404(project_id: str, batch_id: str, db: Session) -> Batch:
    """Fetch a Batch by (project_id, batch_id) or raise HTTP 404.

    Args:
        project_id: Project the batch belongs to.
        batch_id: Identifier of the batch to look up.
        db: Active database session.

    Returns:
        The matching Batch row.

    Raises:
        HTTPException: 404 when no batch with the given ids exists.
    """
    batch = db.scalar(
        select(Batch).where(
            Batch.project_id == project_id,
            Batch.id == batch_id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id!r} not found")
    return batch


def _format_duration(secs: float | None) -> str:
    """Format a duration in seconds to a ``"Xm00s"`` display string.

    Args:
        secs: Duration in seconds, or None for an empty result.

    Returns:
        Formatted string such as ``"2m35s"``, or ``""`` when secs is None.
    """
    if secs is None:
        return ""
    mins = int(secs // 60)
    s = int(secs % 60)
    return f"{mins}m{s:02d}s"


def _batch_item_rows(
    project_id: str,
    batch_id: str,
    db: Session,
    scope_statuses: dict[str, ScopeStatus] | None = None,
    _held_reasons: dict[str, str] | None = None,
) -> list[BatchItemRow]:
    """Load all BatchItems for a batch, enriched with work item + step data (C3 fix)."""
    from sqlalchemy import tuple_ as tuple_fn

    batch_items = list(
        db.scalars(
            select(BatchItem)
            .where(
                BatchItem.project_id == project_id,
                BatchItem.batch_id == batch_id,
            )
            .order_by(BatchItem.execution_group, BatchItem.work_item_id)
        ).all()
    )

    if not batch_items:
        return []

    work_item_keys = [(project_id, bi.work_item_id) for bi in batch_items]
    work_items = db.scalars(
        select(WorkItem).where(tuple_fn(WorkItem.project_id, WorkItem.id).in_(work_item_keys))
    ).all()
    work_item_map: dict[tuple[str, str], WorkItem] = {
        (wi.project_id, wi.id): wi for wi in work_items
    }

    steps = db.scalars(
        select(WorkflowStep)
        .where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id.in_([bi.work_item_id for bi in batch_items]),
        )
        .order_by(WorkflowStep.work_item_id, WorkflowStep.step_number)
    ).all()

    steps_map: dict[str, list[WorkflowStep]] = {}
    for s in steps:
        steps_map.setdefault(s.work_item_id, []).append(s)

    # F-00081: pre-fetch runtime option labels for item-level overrides
    item_option_ids = [
        wi.agent_runtime_option_id for wi in work_items if wi.agent_runtime_option_id is not None
    ]
    option_map: dict[int, AgentRuntimeOption] = {}
    if item_option_ids:
        option_map = {
            r.id: r
            for r in db.scalars(
                select(AgentRuntimeOption).where(AgentRuntimeOption.id.in_(item_option_ids))
            ).all()
        }

    # F-00081: which work items have a step-level override
    has_step_override_items: set[str] = set()
    if steps:
        override_rows = db.execute(
            select(WorkflowStep.work_item_id)
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id.in_(list(steps_map.keys())),
                WorkflowStep.agent_runtime_option_id.isnot(None),
            )
            .group_by(WorkflowStep.work_item_id)
        ).all()
        has_step_override_items = {row[0] for row in override_rows}

    # Fix-cycle counts per step (for step_pipeline fix-cycle rerun pills)
    all_step_ids = [s.id for s in steps]
    fix_cycle_counts: dict[int, int] = {}
    if all_step_ids:
        fix_cycle_rows = db.execute(
            select(FixCycle.step_id, func.count(FixCycle.id).label("cnt"))
            .where(FixCycle.step_id.in_(all_step_ids))
            .group_by(FixCycle.step_id)
        ).all()
        fix_cycle_counts = {row.step_id: row.cnt for row in fix_cycle_rows}

    # F-00090 AC7: pre-fetch regression counts in one batched query (avoids N+1)
    # Only merged items can be regression introducers; skip the query entirely when
    # this batch has no merged rows to keep bounded-query guarantees on active batches.
    item_ids_for_badge = [bi.work_item_id for bi in batch_items if bi.status.value == "merged"]
    regression_counts: dict[str, int] = {}
    if item_ids_for_badge:
        regression_counts = _regression_count_for_merge(project_id, item_ids_for_badge, db)

    rows = []
    for bi in batch_items:
        wi = work_item_map.get((project_id, bi.work_item_id))
        title = wi.title if wi else bi.work_item_id

        item_steps = steps_map.get(bi.work_item_id, [])
        step_nodes = []
        for s in item_steps:
            dur_secs = (
                (s.completed_at - s.started_at).total_seconds()
                if s.started_at and s.completed_at
                else None
            )
            dur = _format_duration(dur_secs)
            step_nodes.append(
                StepNode(
                    step_id=s.step_id,
                    agent_label=s.agent_label,
                    status=s.status.value,
                    duration=dur,
                    duration_secs=dur_secs,
                    fix_cycle_count=fix_cycle_counts.get(s.id, 0),
                )
            )

        dur_total: float | None = None
        if bi.started_at and bi.merged_at:
            dur_total = (bi.merged_at - bi.started_at).total_seconds()

        opt_id = wi.agent_runtime_option_id if wi else None
        opt = option_map.get(opt_id) if opt_id else None

        rows.append(
            BatchItemRow(
                item_id=bi.work_item_id,
                title=title,
                execution_group=bi.execution_group,
                status=bi.status.value,
                steps=step_nodes,
                duration_secs=dur_total,
                started_at=bi.started_at,
                started_at_ts=bi.started_at.timestamp() if bi.started_at else None,
                ended_at_ts=bi.merged_at.timestamp() if bi.merged_at else None,
                scope_status=(scope_statuses or {}).get(bi.work_item_id),
                runtime_option_id=opt_id,
                runtime_option_cli_label=opt.cli_label if opt else None,
                runtime_option_model_label=opt.model_label if opt else None,
                has_step_override=bi.work_item_id in has_step_override_items,
                regression_count=regression_counts.get(bi.work_item_id, 0),
            )
        )
    return rows


def _cascade_counts_for_batches(
    project_id: str, batch_ids: list[str], db: Session
) -> dict[str, int]:
    """C.4: Return {batch_id: count_of_items_with_cascade_events} in one query.

    Joins batch_items → daemon_events filtering to replay event types. Groups
    by batch_id to produce a denormalised count without schema changes.
    """
    from sqlalchemy import func

    if not batch_ids:
        return {}

    replay_types = ("cascaded_replay_after_fix", "review_replay_after_fix")

    # Subquery: distinct work_item_ids that have at least one cascade event
    # within the given batches.
    subq = (
        select(
            BatchItem.batch_id,
            func.count(BatchItem.work_item_id.distinct()).label("cascade_items"),
        )
        .join(
            DaemonEvent,
            (DaemonEvent.entity_id == BatchItem.work_item_id)
            & (DaemonEvent.event_type.in_(replay_types)),
        )
        .where(
            BatchItem.project_id == project_id,
            BatchItem.batch_id.in_(batch_ids),
        )
        .group_by(BatchItem.batch_id)
        .subquery()
    )
    rows = db.execute(select(subq.c.batch_id, subq.c.cascade_items)).all()
    return {row.batch_id: row.cascade_items for row in rows}


def _all_batches(project_id: str, db: Session, status_filter: list[str]) -> list[BatchRow]:
    """Load all batches for a project, enriched with item counts and cascade data.

    Args:
        project_id: Project to query batches for.
        db: Active database session.
        status_filter: Optional list of status strings to restrict results.
            Unknown statuses are silently ignored.

    Returns:
        List of BatchRow instances ordered by creation date descending.
    """
    stmt = select(Batch).where(Batch.project_id == project_id).order_by(Batch.created_at.desc())
    valid = [s for s in status_filter if s in _ALL_STATUSES]
    if valid:
        with contextlib.suppress(ValueError):
            stmt = stmt.where(Batch.status.in_([BatchStatus(s) for s in valid]))

    batches = list(db.scalars(stmt).all())
    batch_ids = [b.id for b in batches]
    step_progress = compute_batch_step_progress(project_id, batch_ids, db)
    # C.4: cascade item counts per batch (single query)
    cascade_counts = _cascade_counts_for_batches(project_id, batch_ids, db)

    rows = []
    for batch in batches:
        items = list(
            db.scalars(
                select(BatchItem).where(
                    BatchItem.project_id == project_id,
                    BatchItem.batch_id == batch.id,
                )
            ).all()
        )
        total_items = len(items)
        completed_items = sum(1 for it in items if it.status.value in ("completed", "merged"))

        pct = step_progress.get(batch.id, 0)

        dur: float | None = None
        if batch.created_at and batch.completed_at:
            dur = (batch.completed_at - batch.created_at).total_seconds()
        rows.append(
            BatchRow(
                id=batch.id,
                status=batch.status.value,
                total_items=total_items,
                completed_items=completed_items,
                progress_pct=pct,
                created_at=batch.created_at,
                duration_secs=dur,
                cascade_item_count=cascade_counts.get(batch.id, 0),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/batches", response_class=HTMLResponse)
def batch_list(
    project_id: str,
    request: Request,
    status: list[str] = Query(default=[]),
    db: Session = Depends(get_db),
) -> Any:
    """Render the batch list page for a project.

    Args:
        project_id: Project whose batches are listed.
        request: Incoming FastAPI request (used to resolve templates).
        status: Optional status filter values appended as query parameters.
        db: Active database session.

    Returns:
        Full-page HTML response for ``pages/project/batches.html``.
    """
    project = _get_project_or_404(project_id, db)
    batches = _all_batches(project_id, db, status_filter=status)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/batches.html",
        {
            "current_project": project,
            "running_count": 0,
            "batches": batches,
            "status_filter": status,
            "visible_statuses": _VISIBLE_STATUSES,
            "active_statuses": _ACTIVE_STATUSES,
        },
    )


@router.get("/batch/{batch_id}", response_class=HTMLResponse)
def batch_detail(
    project_id: str,
    batch_id: str,
    request: Request,
    tab: str = "plan",
    db: Session = Depends(get_db),
) -> Any:
    """Render the batch detail page with items, plan, timeline, and logs tabs.

    Args:
        project_id: Project the batch belongs to.
        batch_id: Batch to display.
        request: Incoming FastAPI request (used to resolve templates).
        tab: Active tab name; falls back to ``"items"`` when the plan tab is
            requested but no execution plan exists yet.
        db: Active database session.

    Returns:
        Full-page HTML response for ``pages/project/batch_detail.html``.
    """
    project = _get_project_or_404(project_id, db)
    batch = _get_batch_or_404(project_id, batch_id, db)
    item_ids = [
        bi.work_item_id
        for bi in db.scalars(
            select(BatchItem).where(
                BatchItem.project_id == project_id, BatchItem.batch_id == batch_id
            )
        ).all()
    ]
    scope_statuses = _get_scope_statuses(project_id, item_ids, db)
    items = _batch_item_rows(project_id, batch_id, db, scope_statuses=scope_statuses)

    dur: float | None = None
    if batch.created_at and batch.completed_at:
        dur = (batch.completed_at - batch.created_at).total_seconds()

    # Render execution plan markdown to HTML if present
    plan_html: str | None = None
    if batch.execution_plan_md:
        import markdown as md

        plan_html = md.markdown(
            batch.execution_plan_md,
            extensions=["tables", "fenced_code"],
        )

    has_plan = batch.execution_plan_md is not None
    has_diagram = batch.execution_plan_png is not None

    # Fall back to items if plan tab requested but no plan exists yet
    if tab == "plan" and not has_plan:
        tab = "items"

    # Compute gantt bounds for the timeline tab
    import datetime as _dt

    gantt_start_ts: float | None = None
    gantt_end_ts: float | None = None
    gantt_total_secs: float | None = None
    started_ts_list = [r.started_at_ts for r in items if r.started_at_ts is not None]
    ended_ts_list = [r.ended_at_ts for r in items if r.ended_at_ts is not None]
    if started_ts_list:
        gantt_start_ts = min(started_ts_list)
        if ended_ts_list:
            gantt_end_ts = max(ended_ts_list)
            # Extend to now if any item is still running
            if any(r.started_at_ts and not r.ended_at_ts for r in items):
                gantt_end_ts = max(gantt_end_ts, _dt.datetime.now(_dt.UTC).timestamp())
        else:
            gantt_end_ts = _dt.datetime.now(_dt.UTC).timestamp()
        gantt_total_secs = gantt_end_ts - gantt_start_ts if gantt_end_ts else None

    # Fetch dispatcher events for the logs tab
    batch_events: list[DaemonEvent] = []
    if tab == "logs":
        # Collect work item IDs belonging to this batch
        item_ids = [row.item_id for row in items]
        # Query events where entity_id is the batch itself or any of its items
        entity_ids = [batch_id, *item_ids]
        batch_events = list(
            db.scalars(
                select(DaemonEvent)
                .where(
                    DaemonEvent.project_id == project_id,
                    DaemonEvent.entity_id.in_(entity_ids),
                )
                .order_by(DaemonEvent.created_at.desc())
            ).all()
        )

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/batch_detail.html",
        {
            "current_project": project,
            "running_count": 0,
            "batch": batch,
            "batch_status": batch.status.value,
            "batch_duration_secs": dur,
            "items": items,
            "active_tab": tab,
            "plan_html": plan_html,
            "has_plan": has_plan,
            "has_diagram": has_diagram,
            "batch_events": batch_events,
            "gantt_start_ts": gantt_start_ts,
            "gantt_end_ts": gantt_end_ts,
            "gantt_total_secs": gantt_total_secs,
        },
    )


@router.get("/batches/fragment", response_class=HTMLResponse)
def batch_list_fragment(
    project_id: str,
    request: Request,
    status: list[str] = Query(default=[]),
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: returns only the batches tbody rows for live refresh."""
    _get_project_or_404(project_id, db)
    batches = _all_batches(project_id, db, status_filter=status)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/batches_table_rows.html",
        {
            "current_project": db.scalar(select(Project).where(Project.id == project_id)),
            "batches": batches,
            "status_filter": status,
        },
    )


@router.get("/batch/{batch_id}/fragment/items", response_class=HTMLResponse)
def batch_items_fragment(
    project_id: str,
    batch_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: returns only the batch items tbody rows for live refresh."""
    project = _get_project_or_404(project_id, db)
    batch = _get_batch_or_404(project_id, batch_id, db)
    item_ids = [
        bi.work_item_id
        for bi in db.scalars(
            select(BatchItem).where(
                BatchItem.project_id == project_id, BatchItem.batch_id == batch_id
            )
        ).all()
    ]
    scope_statuses = _get_scope_statuses(project_id, item_ids, db)
    items = _batch_item_rows(project_id, batch_id, db, scope_statuses=scope_statuses)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/batch_items_rows.html",
        {
            "current_project": project,
            "items": items,
            "batch": batch,
        },
    )


@router.get("/batch/{batch_id}/fragment/header", response_class=HTMLResponse)
def batch_detail_header_fragment(
    project_id: str,
    batch_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx fragment: returns batch detail header for live refresh."""
    project = _get_project_or_404(project_id, db)
    batch = _get_batch_or_404(project_id, batch_id, db)
    item_ids = [
        bi.work_item_id
        for bi in db.scalars(
            select(BatchItem).where(
                BatchItem.project_id == project_id, BatchItem.batch_id == batch_id
            )
        ).all()
    ]
    scope_statuses = _get_scope_statuses(project_id, item_ids, db)
    items = _batch_item_rows(project_id, batch_id, db, scope_statuses=scope_statuses)

    dur: float | None = None
    if batch.created_at and batch.completed_at:
        dur = (batch.completed_at - batch.created_at).total_seconds()

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/batch_detail_header.html",
        {
            "current_project": project,
            "batch": batch,
            "batch_status": batch.status.value,
            "batch_duration_secs": dur,
            "items": items,
        },
    )


@router.get("/batch/{batch_id}/diagram.png")
def batch_diagram_png(
    project_id: str,
    batch_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Serve the execution plan PNG image."""
    from fastapi.responses import Response as FastAPIResponse

    batch = _get_batch_or_404(project_id, batch_id, db)
    if batch.execution_plan_png is None:
        raise HTTPException(status_code=404, detail="No diagram available")
    return FastAPIResponse(
        content=batch.execution_plan_png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/batch/{batch_id}/diagram.drawio")
def batch_diagram_drawio(
    project_id: str,
    batch_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Download the draw.io XML file."""
    from fastapi.responses import Response as FastAPIResponse

    batch = _get_batch_or_404(project_id, batch_id, db)
    if batch.execution_plan_drawio is None:
        raise HTTPException(status_code=404, detail="No diagram available")
    return FastAPIResponse(
        content=batch.execution_plan_drawio,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{batch_id}-execution-plan.drawio"',
        },
    )


# ---------------------------------------------------------------------------
# CR-00078: Overlap ignore endpoints (batches.py — shares path prefix)
# ---------------------------------------------------------------------------


def _get_item_scope_events(
    project_id: str,
    held_item_id: str,
    db: Session,
    window_secs: int = 300,
) -> list[DaemonEvent]:
    """Fetch recent item_held_for_scope events for a work item.

    Mirrors the event query in _get_scope_statuses so the same 300s window
    and event ordering is used for ignore-all logic.
    """
    from datetime import timedelta

    cutoff = datetime.now(UTC) - timedelta(seconds=window_secs)
    return list(
        db.scalars(
            select(DaemonEvent)
            .where(
                DaemonEvent.project_id == project_id,
                DaemonEvent.event_type == "item_held_for_scope",
                DaemonEvent.entity_id == held_item_id,
                DaemonEvent.entity_type == "work_item",
                DaemonEvent.created_at >= cutoff,
            )
            .order_by(DaemonEvent.created_at.desc())
        ).all()
    )


def _overlap_window_cutoff(window_secs: int = 300) -> datetime:
    """Return the UTC datetime cutoff for the overlap event window."""
    from datetime import timedelta as td

    return datetime.now(UTC) - td(seconds=window_secs)


@router.get(
    "/batch/{batch_id}/overlap/{held_item_id}",
    response_class=HTMLResponse,
)
def overlap_modal(
    project_id: str,
    batch_id: str,
    held_item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """htmx modal: read-only overlap details grouped by blocking item.

    CR-00077 S01: returns a modal fragment listing every conflicting glob
    per blocking item, without truncation, grouped by blocking_item_id.
    Returns HTTP 404 when no recent `item_held_for_scope` event exists for
    the given (batch_id, held_item_id) within the 300-second window.
    """
    project = _get_project_or_404(project_id, db)
    _get_batch_or_404(project_id, batch_id, db)

    # Query recent item_held_for_scope events for this held item
    # (same window as _get_scope_statuses)
    cutoff = _overlap_window_cutoff()
    events = (
        db.execute(
            select(DaemonEvent)
            .where(
                DaemonEvent.project_id == project_id,
                DaemonEvent.event_type == "item_held_for_scope",
                DaemonEvent.entity_id == held_item_id,
                DaemonEvent.entity_type == "work_item",
                DaemonEvent.created_at >= cutoff,
            )
            .order_by(DaemonEvent.created_at.desc())
        )
        .scalars()
        .all()
    )

    # 404 when no recent event found
    if not events:
        templates: Jinja2Templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "fragments/batch_overlap_modal.html",
            {"empty": True, "held_item_id": held_item_id, "current_project": project},
            status_code=404,
        )

    # Group events by blocking_item_id (first occurrence wins per blocking_item_id)
    # Also filter out globs that are already recorded in BatchOverlapIgnore
    sections: list[dict[str, Any]] = []
    for blocking_id, globs in group_overlap_events(list(events)):
        # Load ignored globs for this (held_item_id, blocking_id) pair so we can
        # filter them from the modal display (CR-00078 wires the ignore row
        # storage here; the endpoint itself is CR-00077).
        ignored_patterns: set[str] = set()
        if True:  # always-on: no performance concern for a single-held-item modal
            from orch.db.models import BatchOverlapIgnore

            ignored_rows = db.scalars(
                select(BatchOverlapIgnore.file_pattern).where(
                    BatchOverlapIgnore.project_id == project_id,
                    BatchOverlapIgnore.batch_id == batch_id,
                    BatchOverlapIgnore.held_item_id == held_item_id,
                    BatchOverlapIgnore.blocking_item_id == blocking_id,
                )
            ).all()
            ignored_patterns = set(ignored_rows)

        visible_globs = [g for g in globs if g not in ignored_patterns]
        if not visible_globs:
            continue  # skip sections where all files are already ignored

        # Fetch the blocking item's title; use blocking_id as fallback
        blocking_wi = db.get(WorkItem, (project_id, blocking_id))
        blocking_title = blocking_wi.title if blocking_wi else blocking_id
        sections.append(
            {
                "blocking_item_id": blocking_id,
                "blocking_item_title": blocking_title,
                "globs": visible_globs,
            }
        )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/batch_overlap_modal.html",
        {
            "empty": False,
            "held_item_id": held_item_id,
            "project_id": project_id,
            "current_project": project,
            "sections": sections,
        },
    )
